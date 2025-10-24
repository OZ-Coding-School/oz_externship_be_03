from typing import Dict, Optional

from django.db.models import QuerySet
from implicit.cpu.als import AlternatingLeastSquares  # type: ignore
from scipy.sparse import csr_matrix  # 타입 힌트를 위해 추가

from apps.lecture.models import CrawledLecture, LectureBookmark
from apps.lecture.services.constants import INTERACTION_WEIGHTS, RATING_SCORE_MAP
from apps.lecture.services.data_loader import DataLoader
from apps.lecture.services.model_trainer import ModelTrainer


class RecommendationService:
    """
    강의 추천 서비스를 제공하는 메인 클래스.
    모델 메모리 캐싱, 콜드 스타트 폴백을 적용.
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
        모델이 메모리에 로드되어 있는지 확인. 없으면 로드하여 캐싱.
        매 요청마다 디스크 I/O를 방지하는 캐싱 구현.
        """
        if self._model is not None:
            return True

        # 1. 모델과 매핑 로드
        model, u_to_i, l_to_i, _, _ = self.model_trainer.load_model_and_mappings()

        if model is None:
            return False

        # 2. 훈련에 사용된 전체 상호작용 행렬 (user_items) 생성 및 캐싱
        interaction_matrix, _, _, _, _ = self.data_loader.build_user_item_matrix()

        if interaction_matrix is None:
            print("Could not load interaction matrix for recommender.")
            return False

        user_items_csr = interaction_matrix.tocsr()

        assert l_to_i is not None

        # 성공적으로 로드 시 인스턴스 변수에 캐싱
        self._model = model
        self._user_to_idx = u_to_i
        self._lecture_to_idx = l_to_i
        self._lecture_idx_to_id = {v: k for k, v in l_to_i.items()}
        self._user_items_matrix = user_items_csr
        return True

    def recommend_lectures_for_user(self, user_id: int, top_n: int = 5) -> Optional[QuerySet[CrawledLecture]]:
        """
        특정 사용자 대상 Top-N 맞춤 강의 추천 반환.
        """
        # 1. 모델 로드 확인 및 콜드 스타트/폴백 처리
        if not self._ensure_model_loaded() or self._user_to_idx is None or user_id not in self._user_to_idx:
            # 모델 로드 실패 또는 신규 사용자(콜드 스타트)인 경우 폴백
            return self._get_popular_lectures(top_n)

        assert self._model is not None
        assert self._user_to_idx is not None
        assert self._lecture_to_idx is not None
        assert self._lecture_idx_to_id is not None
        assert self._user_items_matrix is not None

        model = self._model
        user_to_idx = self._user_to_idx
        lecture_to_idx = self._lecture_to_idx
        lecture_idx_to_id = self._lecture_idx_to_id
        user_items_matrix = self._user_items_matrix  # 변수 할당

        user_index = user_to_idx[user_id]

        # 2. 필터링할 항목(이미 좋아요 누른 항목) 인덱스 조회
        liked_lecture_ids = LectureBookmark.objects.filter(user_id=user_id).values_list("lecture_id", flat=True)
        # 좋아요 누른 강의 ID를 모델 인덱스로 변환
        liked_indices = [lecture_to_idx[lec_id] for lec_id in liked_lecture_ids if lec_id in lecture_to_idx]

        # 3. 추천 계산 (user_items 인자 추가)
        recommended = model.recommend(
            user_index,
            user_items_matrix,
            N=top_n,
            filter_items=liked_indices,
        )

        # 4. 결과 변환 및 QuerySet 반환
        # 추천된 인덱스를 실제 강의 ID로 변환
        recommended_ids = [lecture_idx_to_id[item[0]] for item in recommended if item[0] in lecture_idx_to_id]

        if not recommended_ids:
            return self._get_popular_lectures(top_n)

        # Django ORM을 사용하여 강의 정보 조회 및 카테고리 프리패치
        lectures = CrawledLecture.objects.filter(id__in=recommended_ids).prefetch_related(
            "lecture_categories__category"
        )

        return lectures

    def _get_popular_lectures(self, top_n: int) -> QuerySet[CrawledLecture]:
        """모델 실패 또는 콜드 스타트 시 인기순 폴백 제공."""
        print("Fallback to popular lectures due to cold start/model failure.")
        # average_rating 기준으로 정렬하여 반환
        return CrawledLecture.objects.order_by("-average_rating")[:top_n]
