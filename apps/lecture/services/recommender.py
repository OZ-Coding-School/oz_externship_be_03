import logging
import pickle
from typing import Dict, Optional

from django.core.cache import cache
from django.db.models import Case, IntegerField, QuerySet, Value, When
from implicit.als import AlternatingLeastSquares  # type: ignore
from scipy.sparse import csr_matrix

from apps.lecture.models import CrawledLecture, LectureBookmark
from apps.lecture.services.constants import (
    ALS_MODEL_CACHE_KEY,
    INTERACTION_WEIGHTS,
    L_IDX_TO_ID_CACHE_KEY,
    L_TO_IDX_CACHE_KEY,
    MODEL_CACHE_TIMEOUT,
    POPULAR_LECTURE_ORDER_BY,
    RATING_SCORE_MAP,
    U_TO_IDX_CACHE_KEY,
    USER_ITEMS_MATRIX_CACHE_KEY,
)
from apps.lecture.services.data_loader import DataLoader
from apps.lecture.services.model_trainer import ModelTrainer

logger = logging.getLogger(__name__)


class RecommendationService:
    """
    강의 추천 서비스를 제공하는 메인 클래스.
    모델 Redis 캐싱, 콜드 스타트 폴백 적용, 다중 워커 환경에 최적화.
    """

    def __init__(self) -> None:
        """RecommendationService 인스턴스 초기화 및 의존성 주입."""
        self.data_loader = DataLoader(weights=INTERACTION_WEIGHTS, rating_map=RATING_SCORE_MAP)
        self.model_trainer = ModelTrainer(data_loader=self.data_loader)

        # 모델 및 매핑 정보를 메모리에 캐싱하기 위한 변수
        self._model: Optional[AlternatingLeastSquares] = None
        self._user_to_idx: Optional[Dict[int, int]] = None
        self._lecture_to_idx: Optional[Dict[int, int]] = None
        self._lecture_idx_to_id: Optional[Dict[int, int]] = None
        self._user_items_matrix: Optional[csr_matrix] = None

    def _ensure_model_loaded(self) -> bool:
        """
        모델이 메모리에 로드되어 있는지 확인. 없으면 Redis에서 로드하거나,
        디스크에서 로드 후 Redis에 캐싱.
        """
        # 1. 이미 요청 기간 동안 메모리에 로드된 경우 바로 반환
        if self._model is not None:
            return True

        # 2. Redis에서 캐시 데이터 로드 시도
        cached_data = None
        try:
            cached_data = cache.get_many(
                [
                    ALS_MODEL_CACHE_KEY,
                    U_TO_IDX_CACHE_KEY,
                    L_TO_IDX_CACHE_KEY,
                    L_IDX_TO_ID_CACHE_KEY,
                    USER_ITEMS_MATRIX_CACHE_KEY,
                ]
            )
        except Exception as e:
            # Redis 오류 발생 시, 로깅 후 디스크 로드로 폴백 (cached_data는 None 유지)
            logger.error(f"Redis get_many error: {e}. Falling back to disk load.")

        # 3. Redis 캐시가 모두 존재하고 손상되지 않았으면 역직렬화하여 메모리 변수에 할당
        if cached_data and all(
            key in cached_data and cached_data[key] is not None
            for key in [
                ALS_MODEL_CACHE_KEY,
                U_TO_IDX_CACHE_KEY,
                L_TO_IDX_CACHE_KEY,
                L_IDX_TO_ID_CACHE_KEY,
                USER_ITEMS_MATRIX_CACHE_KEY,
            ]
        ):
            try:
                self._model = pickle.loads(cached_data[ALS_MODEL_CACHE_KEY])
                self._user_to_idx = pickle.loads(cached_data[U_TO_IDX_CACHE_KEY])
                self._lecture_to_idx = pickle.loads(cached_data[L_TO_IDX_CACHE_KEY])
                self._lecture_idx_to_id = pickle.loads(cached_data[L_IDX_TO_ID_CACHE_KEY])
                self._user_items_matrix = pickle.loads(cached_data[USER_ITEMS_MATRIX_CACHE_KEY])
                return True
            except (pickle.UnpicklingError, TypeError, EOFError) as e:
                logger.error(f"Redis deserialization error. Deleting cache: {e}")
                # 역직렬화 오류 시 캐시 삭제 및 재로드를 위해 디스크 로드로 폴백
                cache.delete_many(cached_data.keys())
                # cached_data가 유효하지 않으므로, 다음 단계(디스크 로드)로 넘어감

        # 4. Redis에 캐시가 없거나 오류/손상되었으면 디스크에서 모델 로드 (ModelTrainer)
        model, u_to_i, l_to_i, _, _ = self.model_trainer.load_model_and_mappings()
        if model is None:
            return False
        if u_to_i is None or l_to_i is None:
            logger.error("Could not load model mappings (u_to_i or l_to_i).")
            return False

        # 5. 상호작용 행렬 생성 (DataLoader)
        interaction_matrix, _, _, _, _ = self.data_loader.build_user_item_matrix()
        if interaction_matrix is None:
            logger.error("Could not load interaction matrix for recommender.")
            return False

        user_items_csr = interaction_matrix.tocsr()
        lecture_idx_to_id = {v: k for k, v in l_to_i.items()}

        # 6. 메모리 변수에 할당 (현재 요청 처리용)
        self._model = model
        self._user_to_idx = u_to_i
        self._lecture_to_idx = l_to_i
        self._lecture_idx_to_id = lecture_idx_to_id
        self._user_items_matrix = user_items_csr

        # 7. Redis에 직렬화하여 캐싱 (다른 워커들을 위해)
        try:
            cache.set_many(
                {
                    ALS_MODEL_CACHE_KEY: pickle.dumps(model),
                    U_TO_IDX_CACHE_KEY: pickle.dumps(u_to_i),
                    L_TO_IDX_CACHE_KEY: pickle.dumps(l_to_i),
                    L_IDX_TO_ID_CACHE_KEY: pickle.dumps(lecture_idx_to_id),
                    USER_ITEMS_MATRIX_CACHE_KEY: pickle.dumps(user_items_csr),
                },
                MODEL_CACHE_TIMEOUT,
            )
        except Exception as e:
            # 캐싱 실패하더라도 현재 워커의 메모리 변수는 유효하므로 True 반환
            logger.error(f"Redis set_many error: {e}")

        return True

    def recommend_lectures_for_user(self, user_id: int, top_n: int = 5) -> Optional[QuerySet[CrawledLecture]]:
        """
        특정 사용자 대상 Top-N 맞춤 강의 추천 반환.
        """
        # 1. 모델 로드 확인 및 콜드 스타트/폴백 처리
        if not self._ensure_model_loaded() or self._user_to_idx is None or user_id not in self._user_to_idx:
            # 모델 로드 실패 또는 신규 사용자(콜드 스타트)인 경우 폴백
            return self._get_popular_lectures(user_id, top_n)

        # 모델이 로드되었으므로, 캐시된 변수 사용
        model = self._model
        user_to_idx = self._user_to_idx
        lecture_to_idx = self._lecture_to_idx
        lecture_idx_to_id = self._lecture_idx_to_id
        user_items_matrix = self._user_items_matrix

        assert model is not None
        assert user_to_idx is not None
        assert lecture_to_idx is not None
        assert lecture_idx_to_id is not None
        assert user_items_matrix is not None

        user_index = user_to_idx[user_id]

        # 2. 필터링할 항목(이미 좋아요 누른 항목) 인덱스 조회
        liked_lecture_ids = LectureBookmark.objects.filter(user_id=user_id).values_list("lecture_id", flat=True)
        # 좋아요 누른 강의 ID를 모델 인덱스로 변환
        liked_indices = [lecture_to_idx[lec_id] for lec_id in liked_lecture_ids if lec_id in lecture_to_idx]

        # 3. 추천 계산
        recommended = model.recommend(
            user_index,
            user_items_matrix,
            N=top_n,
            filter_items=liked_indices,
        )

        # 4. 결과 변환 및 QuerySet 반환
        # 추천된 인덱스를 실제 강의 ID로 변환
        recommended_ids = [lecture_idx_to_id[item[0]] for item in recommended if item[0] in lecture_idx_to_id]

        # 모델이 요청된 개수(top_n) 미만을 반환하면 폴백으로 대체
        if len(recommended_ids) < top_n:
            logger.error(f"Fallback due to insufficient recommendation results: {len(recommended_ids)} < {top_n}")
            return self._get_popular_lectures(user_id, top_n)

        # Django ORM을 사용하여 강의 정보 조회 및 카테고리 프리패치
        lectures = (
            CrawledLecture.objects.filter(id__in=recommended_ids)
            .prefetch_related("lecture_categories__category")
            .order_by(
                Case(
                    *[When(id=pk, then=Value(i)) for i, pk in enumerate(recommended_ids)],
                    output_field=IntegerField(),
                )
            )
        )
        return lectures

    def _get_popular_lectures(self, user_id: int, top_n: int) -> QuerySet[CrawledLecture]:
        """모델 실패 또는 콜드 스타트 시 인기순 폴백 제공 (북마크 제외)."""
        logger.error("Fallback to popular lectures due to cold start/model failure.")

        liked_lecture_ids = LectureBookmark.objects.filter(user_id=user_id).values_list("lecture_id", flat=True)

        queryset = (
            CrawledLecture.objects.exclude(id__in=liked_lecture_ids)
            .prefetch_related("lecture_categories__category")
            .order_by(POPULAR_LECTURE_ORDER_BY, "id")
        )

        result_qs = queryset[:top_n]

        return result_qs
