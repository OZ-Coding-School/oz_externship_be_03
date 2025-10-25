import json
import logging
import pickle
import random
import time
from datetime import datetime
from random import sample
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Union,
    cast,
)

import numpy as np
from django.conf import settings
from django.core.cache import cache
from django.db.models import (
    Avg,
    Case,
    FloatField,
    IntegerField,
    QuerySet,
    Value,
    When,
)
from django.db.models.functions import Cast
from django_redis import get_redis_connection  # type: ignore
from implicit.als import AlternatingLeastSquares  # type: ignore
from scipy.sparse import csr_matrix

from apps.lecture.models import CrawledLecture, LectureCategory, UserPreferCategory
from apps.lecture.services.constants import (
    ALS_MODEL_CACHE_KEY,
    ALS_SCORE_POWER_DECAY,
    ALS_TRAINING_LOCK_KEY,
    CATEGORY_MATCH_BONUS,
    INITIAL_BACKOFF_SECONDS,
    L_IDX_TO_ID_CACHE_KEY,
    L_TO_IDX_CACHE_KEY,
    LECTURE_METADATA_CACHE_KEY,
    LECTURE_METADATA_TTL,
    MAX_CACHE_LOAD_RETRIES,
    MODEL_CACHE_TIMEOUT,
    NORMALIZE_ALS_SCORE,
    POPULAR_LECTURE_ORDER_BY,
    REVIEW_RATING_MULTIPLIER,
    U_TO_IDX_CACHE_KEY,
    USER_ITEMS_MATRIX_CACHE_KEY,
)
from apps.lecture.services.data_loader import DataLoader
from apps.lecture.services.model_trainer import ModelBundleReturn, ModelTrainer

logger = logging.getLogger(__name__)

# 타입 힌팅 정의
LectureQuerySet = QuerySet[CrawledLecture]
# 강의 메타데이터 타입: (평점, {카테고리 ID 집합})
LectureMetadata = Tuple[float, Set[int]]
# Redis Connection Type (Django Redis)
RedisConnection = Any


class RecommendationService:
    """ALS 기반 추천 로직 및 콜드 스타트/안정성 관리 클래스"""

    # Redis ping 주기: Redis 상태를 재확인하는 간격 (1시간)
    REDIS_PING_INTERVAL_SECONDS: int = 60 * 60

    def __init__(self) -> None:
        """RecommendationService 초기화: 데이터 로더, 트레이너, 모델 컴포넌트, Redis 연결 설정"""
        self.data_loader: DataLoader = DataLoader()
        self.model_trainer: ModelTrainer = ModelTrainer(self.data_loader)

        # 모델 컴포넌트 (메모리 캐시)
        self._model: Optional[AlternatingLeastSquares] = None
        self._user_to_idx: Optional[Dict[int, int]] = None
        self._lecture_to_idx: Optional[Dict[int, int]] = None
        self._lecture_idx_to_id: Optional[Dict[int, int]] = None
        self._user_items_matrix: Optional[csr_matrix] = None
        self._last_trained_at: Optional[datetime] = None

        # Redis 연결 인스턴스 초기화 및 상태 점검
        self.redis_conn: Optional[RedisConnection] = self._get_redis_cache()

        # Redis health flag 및 마지막 핑 시간 기록
        # init 시 로그는 억제 (False)
        self.redis_healthy: bool = self._check_redis_health(log_status=False)
        self.last_ping: float = time.time()

    # -- 1. 모델 로드/캐시 관리 (Model Load/Cache Management)

    def _get_redis_cache(self) -> Optional[RedisConnection]:
        """Django Redis Cache 인스턴스를 가져옵니다."""
        try:
            # "default"는 settings.py의 CACHES 설정에 정의된 별칭
            return get_redis_connection("default")
        except Exception as e:
            logger.error(f"[CACHE] Redis connection failed during init: {e}. Falling back to Django cache.")
            return None

    def _check_redis_health(self, log_status: bool = True) -> bool:
        """Redis 연결 상태(ping)를 확인하고 상태 플래그 설정"""
        if not self.redis_conn:
            return False

        try:
            if self.redis_conn.ping():
                if log_status:
                    logger.info("[CACHE] Redis health check OK.")
                return True
            else:
                if log_status:
                    logger.warning("[CACHE] Redis PING failed, connection unstable. Falling back to Django cache.")
                return False
        except Exception as e:
            if log_status:
                logger.warning(f"[CACHE] Redis connection error during PING: {e}. Falling back to Django cache.")
            return False

    def _is_redis_ready(self) -> bool:
        """
        주기적으로 Redis 상태를 재확인하고 연결 상태 반환.
        health check 오버헤드를 줄이기 위한 로직 포함.
        """
        current_time: float = time.time()

        if self.redis_healthy and (current_time - self.last_ping < self.REDIS_PING_INTERVAL_SECONDS):
            # 건강하고, 재확인 주기 전이라면 통과
            return True

        # 재확인 주기 도래 또는 현재 건강하지 않음: 상태 재확인 시도
        if self.redis_healthy:
            # 건강했으나 재확인 주기 도래
            log_message = "[CACHE] Redis re-checking health."
            status_check_interval = self.REDIS_PING_INTERVAL_SECONDS
        else:
            # 현재 건강하지 않다면, 복구되었는지 확인 (복구 시도는 1분에 한 번만)
            if current_time - self.last_ping < 60:
                return False
            log_message = "[CACHE] Redis attempting recovery check."
            status_check_interval = 60

        if current_time - self.last_ping >= status_check_interval:
            new_status: bool = self._check_redis_health()
            self.redis_healthy = new_status
            self.last_ping = current_time
            if new_status and not self.redis_healthy:
                logger.info("[CACHE] Redis connection recovered.")
            return new_status

        return self.redis_healthy

    def _load_from_redis(self) -> bool:
        """
        Redis 캐시에서 모델 컴포넌트 로드.
        """
        if not self._is_redis_ready():
            return False

        keys: List[str] = [
            ALS_MODEL_CACHE_KEY,
            U_TO_IDX_CACHE_KEY,
            L_TO_IDX_CACHE_KEY,
            L_IDX_TO_ID_CACHE_KEY,
            USER_ITEMS_MATRIX_CACHE_KEY,
        ]

        try:
            # Django cache.get_many() 사용
            cached_data: Dict[str, Union[bytes, None, str]] = cache.get_many(keys)

            if all(key in cached_data and cached_data[key] is not None for key in keys):
                # pickle.loads 시 타입을 bytes로 명시적으로 캐스팅
                self._model = pickle.loads(cast(bytes, cached_data[ALS_MODEL_CACHE_KEY]))
                self._user_to_idx = pickle.loads(cast(bytes, cached_data[U_TO_IDX_CACHE_KEY]))
                self._lecture_to_idx = pickle.loads(cast(bytes, cached_data[L_TO_IDX_CACHE_KEY]))
                self._lecture_idx_to_id = pickle.loads(cast(bytes, cached_data[L_IDX_TO_ID_CACHE_KEY]))
                self._user_items_matrix = pickle.loads(cast(bytes, cached_data[USER_ITEMS_MATRIX_CACHE_KEY]))

                loaded_matrix = pickle.loads(cast(bytes, cached_data[USER_ITEMS_MATRIX_CACHE_KEY]))
                if loaded_matrix is not None:
                    self._user_items_matrix = loaded_matrix.tocsr()  # CSR로 변환
                else:
                    self._user_items_matrix = None
                if settings.DEBUG:
                    logger.debug("[CACHE] Model components loaded from Redis/Django cache.")
                return True
        except Exception as e:
            logger.error(f"[CACHE_FAIL] Redis/Django get/deserialization error: {e}. Invalidating cache.")
            cache.delete_many(keys)
        return False

    def _save_to_redis(self) -> None:
        """현재 메모리 모델 컴포넌트를 Redis 캐시에 저장"""

        if not self._is_redis_ready():
            return

        is_ready: bool = (
            self._model is not None
            and self._user_to_idx is not None
            and self._lecture_to_idx is not None
            and self._lecture_idx_to_id is not None
            and self._user_items_matrix is not None  # None 체크 분리
            and self._user_items_matrix.size > 0  # .size 체크 분리
        )

        if is_ready:
            try:
                # 딕셔너리 형태로 데이터를 직렬화
                data_to_cache: Dict[str, bytes] = {
                    ALS_MODEL_CACHE_KEY: pickle.dumps(self._model),
                    U_TO_IDX_CACHE_KEY: pickle.dumps(self._user_to_idx),
                    L_TO_IDX_CACHE_KEY: pickle.dumps(self._lecture_to_idx),
                    L_IDX_TO_ID_CACHE_KEY: pickle.dumps(self._lecture_idx_to_id),
                    USER_ITEMS_MATRIX_CACHE_KEY: pickle.dumps(self._user_items_matrix),
                }

                cache.set_many(data_to_cache, MODEL_CACHE_TIMEOUT)

            except Exception as e:
                logger.error(f"[CACHE_FAIL] Redis/Django set_many error: {e}")

    def _ensure_model_loaded(self) -> bool:
        """
        모델이 메모리에 로드되었는지 확인하고, 필요 시 Redis 또는 파일에서 로드.
        모델 파일 로드 시에는 Redis 락을 기반으로 동시성 제어.

        :return: 모델 로드 성공 여부
        """
        # 1. 메모리 확인
        if self._model is not None:
            return True
        # 2. Redis 캐시 로드 시도
        if self._load_from_redis():
            return True

        # 3. 파일 로드 및 캐시 저장 시도 (락 기반 동시성 제어)
        for attempt in range(MAX_CACHE_LOAD_RETRIES):
            # Redis 락 획득 시도 (300초 = 5분 타임아웃)
            if cache.add(ALS_TRAINING_LOCK_KEY, True, timeout=300):
                try:
                    # 락 획득 성공: 파일에서 모델 로드
                    model_bundle: ModelBundleReturn = self.model_trainer.load_model_and_mappings()
                    (
                        model,
                        u_to_i,
                        l_to_i,
                        _,
                        _,
                        user_items_matrix,
                        last_trained_at,
                    ) = model_bundle

                    # 필수 컴포넌트 누락 확인
                    if (
                        model is None
                        or u_to_i is None
                        or l_to_i is None
                        or user_items_matrix is None
                        or last_trained_at is None
                    ):
                        logger.error("[FILE] Essential model components missing from disk.")
                        return False

                    # 메모리 업데이트
                    self._model = model
                    self._user_to_idx = u_to_i
                    self._lecture_to_idx = l_to_i
                    # 역방향 매핑 생성
                    self._lecture_idx_to_id = {v: k for k, v in l_to_i.items()}
                    self._user_items_matrix = user_items_matrix
                    self._last_trained_at = last_trained_at

                    # Redis 캐시에 저장
                    self._save_to_redis()
                    return True
                finally:
                    # 락 해제
                    try:
                        cache.delete(ALS_TRAINING_LOCK_KEY)
                    except Exception as e:
                        logger.error(f"[CACHE_FAIL] Failed to release training lock: {e}")
            else:
                # 락 획득 실패: 백오프 대기
                if attempt < MAX_CACHE_LOAD_RETRIES - 1:
                    backoff_time: float = INITIAL_BACKOFF_SECONDS * (2**attempt)
                    # 지터(Jitter) 추가: 0.5 ~ 1.0 범위의 랜덤 값
                    jittered_time: float = backoff_time * (0.5 + random.random() * 0.5)

                    if settings.DEBUG:
                        logger.debug(
                            f"[CACHE] Training lock active. Retrying in {jittered_time:.2f}s (Attempt {attempt + 1})."
                        )
                    time.sleep(jittered_time)
                else:
                    logger.error("[CACHE] Failed to acquire model load lock after multiple retries.")
                    return False

        return False

    # -- 2. 메타데이터 및 리랭킹 (Metadata & Reranking)

    def _get_lecture_metadata_cached(self, lecture_id: int) -> LectureMetadata:
        """
        강의 메타데이터(평점, 카테고리)를 Redis/Django Cache에서 TTL 캐싱하여 가져오거나 DB에서 조회.
        """
        cache_key: str = LECTURE_METADATA_CACHE_KEY.format(lecture_id)
        cached_raw: Union[bytes, str, None] = None

        # 1. Redis/Django Cache에서 로드 시도
        try:
            if self._is_redis_ready() and self.redis_conn is not None:
                cached_raw = self.redis_conn.get(cache_key)
            else:
                cached_raw = cache.get(cache_key)

            if cached_raw:
                if isinstance(cached_raw, bytes):
                    # Redis는 bytes를 반환할 수 있으므로 디코딩
                    cached_raw = cached_raw.decode("utf-8")

                data: Dict[str, Any] = json.loads(cached_raw)
                # 데이터 역직렬화 및 타입 캐스팅
                return (float(data["rating"]), set(data["categories"]))

        except Exception as e:
            logger.warning(f"[META_CACHE] Cache retrieval failed for {lecture_id}: {e}. Falling back to DB.")

        # 2. 캐시 실패 또는 캐시 부재 시 DB 조회
        try:
            # 평점: `average_rating` 필드 또는 `review` 관계를 통한 평균 평점 계산
            lecture_data: Optional[Dict[str, Any]] = (
                CrawledLecture.objects.filter(id=lecture_id)
                # 🚨 수정: Avg를 적용하기 전에 reviews__rating 필드를 FloatField로 Cast합니다.
                .annotate(avg_rating_calculated=Avg(Cast("reviews__rating", output_field=FloatField())))
                .values("average_rating", "avg_rating_calculated")
                .first()
            )

            avg_rating_field: Optional[Union[float, str]] = lecture_data.get("average_rating") if lecture_data else None
            # `average_rating`이 None인 경우 `avg_rating_calculated` 사용
            if avg_rating_field is None:
                avg_rating_field = lecture_data.get("avg_rating_calculated") if lecture_data else None

            avg_rating: float = float(avg_rating_field) if avg_rating_field is not None else 0.0

            # 카테고리 ID 집합 조회
            category_ids: Set[int] = set(
                LectureCategory.objects.filter(lecture_id=lecture_id).values_list("category_id", flat=True)
            )

            # 3. Redis/Django Cache에 저장
            data_to_cache: Dict[str, Union[float, List[int]]] = {
                "rating": avg_rating,
                "categories": list(category_ids),
            }
            json_data: str = json.dumps(data_to_cache)

            try:
                if self._is_redis_ready() and self.redis_conn is not None:
                    # Redis 전용 set 메서드 사용 (TTL 적용)
                    self.redis_conn.set(cache_key, json_data, ex=LECTURE_METADATA_TTL)
                else:
                    # Django Cache Fallback
                    cache.set(cache_key, json_data, LECTURE_METADATA_TTL)
            except Exception as e:
                logger.error(f"[META_CACHE] Error saving to cache for {lecture_id}: {e}")

            return (avg_rating, category_ids)

        except Exception as e:
            logger.error(f"[METADATA] Failed to load metadata for lecture {lecture_id}: {e}")
            return (0.0, set())

    def _get_post_processed_ranking(self, user_id: int, recommended_with_score: List[Tuple[int, float]]) -> List[int]:
        """
        ALS 점수에 메타데이터 가중치를 적용하여 최종 순위 재정렬 (Reranking).

        :param user_id: 현재 사용자 ID
        :param recommended_with_score: ALS가 예측한 (강의 인덱스, 점수) 리스트
        :return: 최종 점수 기준 내림차순 정렬된 강의 ID 리스트
        """

        if not recommended_with_score or self._lecture_idx_to_id is None:  # None 체크 추가
            logger.error("[RERANK] Components missing or no recommendation. Skipping Reranking.")
            return []

        # 사용자 선호 카테고리 조회
        user_prefer_cats: Set[int] = set(
            UserPreferCategory.objects.filter(user_id=user_id).values_list("category_id", flat=True)
        )

        final_scores: List[Tuple[int, float]] = []
        # ALS 점수만 추출하여 numpy 배열로 변환
        als_scores: np.ndarray = np.array([s for _, s in recommended_with_score], dtype=np.float32)

        # 1. ALS 점수 감쇠 및 정규화
        if als_scores.size > 0:
            # 감쇠 적용 (ALS_score ** 0.8)
            processed_als_scores: np.ndarray = np.power(als_scores, ALS_SCORE_POWER_DECAY)

            if NORMALIZE_ALS_SCORE:
                # Min-Max 정규화 [0, 1]
                min_s, max_s = processed_als_scores.min(), processed_als_scores.max()
                ptp_score = max_s - min_s

                if ptp_score > 1e-6:
                    # 정규화: (score - min) / (max - min)
                    normalized_als_scores = (processed_als_scores - min_s) / ptp_score
                else:
                    # Min=Max 일 경우 0으로 설정
                    logger.warning(
                        (
                            "[RERANK] ALS scores Min=Max (%s after decay). "
                            "Setting normalized scores to 0. User Index: %s"
                        ),
                        f"{min_s:.3f}",
                        self._user_to_idx.get(user_id) if self._user_to_idx else "N/A",
                    )
                    normalized_als_scores = processed_als_scores * 0
            else:
                # 정규화 OFF 시, 감쇠된 점수를 그대로 사용
                normalized_als_scores = processed_als_scores
        else:
            normalized_als_scores = np.array([])

        # 2. 메타데이터 가중치 적용
        for i, (idx, _) in enumerate(recommended_with_score):
            # 강의 인덱스 -> 강의 ID
            lec_id: int = self._lecture_idx_to_id[idx]
            # 강의 메타데이터 로드 (평점, 카테고리)
            avg_rating, lec_cats = self._get_lecture_metadata_cached(lec_id)

            # 최종 정규화/감쇠된 ALS 점수
            final_als_score: float = normalized_als_scores[i] if normalized_als_scores.size > 0 else 0.0

            # 평점 가중치: (평점 / 5.0) * REVIEW_RATING_MULTIPLIER
            normalized_rating: float = avg_rating / 5.0
            rating_bonus: float = normalized_rating * REVIEW_RATING_MULTIPLIER

            # 카테고리 매칭 가중치: 일치하는 카테고리 수 * CATEGORY_MATCH_BONUS
            matched_cats: Set[int] = user_prefer_cats.intersection(lec_cats)
            category_bonus: float = len(matched_cats) * CATEGORY_MATCH_BONUS

            # 최종 점수 계산: ALS 점수 + 평점 보너스 + 카테고리 보너스
            final_score: float = final_als_score + rating_bonus + category_bonus

            final_scores.append((lec_id, final_score))

            if settings.DEBUG:
                logger.debug(
                    ("[RECSCORE][U:%s] L:%s: ALS_Final(%.3f) + R(%.3f) + C(%.3f) -> Final(%.3f)"),
                    user_id,
                    lec_id,
                    final_als_score,
                    rating_bonus,
                    category_bonus,
                    final_score,
                )

        # 최종 점수 기준으로 내림차순 정렬 후 강의 ID만 추출
        final_scores.sort(key=lambda x: x[1], reverse=True)
        return [lec_id for lec_id, _ in final_scores]

    # -- 3. 콜드 스타트/폴백 로직 (Cold Start/Fallback Logic)

    def _get_popular_lectures(self, top_n: int) -> LectureQuerySet:
        """전체 인기 강의 기반 폴백 (모델 실패 또는 콜드 스타트 시)"""
        try:
            return (
                CrawledLecture.objects.all()
                .order_by(POPULAR_LECTURE_ORDER_BY)[:top_n]
                .prefetch_related("lecturecategory_set__category")
            )
        except Exception as e:
            logger.error(f"[FALLBACK] Error fetching popular lectures: {e}")
            # 안전 폴백: ID 역순으로 반환
            return (
                CrawledLecture.objects.all().order_by("-id")[:top_n].prefetch_related("lecturecategory_set__category")
            )

    def _get_category_fallback(self, user_id: int, top_n: int) -> LectureQuerySet:
        """
        사용자 선호 카테고리 기반 콜드 스타트/폴백.
        결과가 무작위로 섞여서 반환되도록 처리합니다.
        """
        user_prefer_cats: Set[int] = set(
            UserPreferCategory.objects.filter(user_id=user_id).values_list("category_id", flat=True)
        )

        if not user_prefer_cats:
            # 선호 카테고리 없으면 인기 강의 폴백
            logger.info(f"[COLD_START] User {user_id} has no preferred categories. Using Popular Fallback.")
            return self._get_popular_lectures(top_n)

        # 1. 선호 카테고리에 속하는 강의 필터링 후 인기순 정렬
        filtered_qs: LectureQuerySet = (
            CrawledLecture.objects.filter(lecture_categories__category_id__in=user_prefer_cats)
            .distinct()
            .order_by(POPULAR_LECTURE_ORDER_BY)
        )
        try:
            # 2. 무작위 샘플링을 위한 충분한 풀 확보 (N*2개 ID)
            ids: List[int] = list(filtered_qs.values_list("id", flat=True)[: top_n * 2])

            if not ids:
                return self._get_popular_lectures(top_n)

            # 메모리에서 랜덤 샘플링
            random_ids: List[int] = sample(ids, min(top_n, len(ids)))

            # 3. 최종 쿼리셋 반환
            return CrawledLecture.objects.filter(id__in=random_ids).prefetch_related("lecturecategory_set__category")

        except Exception as e:
            logger.error(f"[FALLBACK] Error fetching category fallback using random.sample: {e}")
            # 안전 폴백: 필터링된 결과에서 인기순으로 top_n 반환
            return filtered_qs[:top_n]

    # -- 4. 메인 추천 함수 (Main Recommendation Function)

    def recommend_lectures(self, user_id: int, top_n: int = 10) -> LectureQuerySet:
        """
        주요 추천 실행 함수. ALS 예측, 후처리, 콜드 스타트 및 폴백 관리.

        :param user_id: 추천을 받을 사용자 ID
        :param top_n: 반환할 추천 강의 수
        :return: 순서가 유지된 CrawledLecture QuerySet
        """
        # 1. 모델 로드 및 사용자 매핑 확인
        if not self._ensure_model_loaded() or self._model is None or self._user_items_matrix is None:
            logger.warning(f"[REC] Model not available for user {user_id}. Using Category Fallback.")
            return self._get_category_fallback(user_id, top_n)

        user_index: Optional[int] = cast(Dict[int, int], self._user_to_idx).get(user_id)
        if user_index is None:
            logger.warning(f"[REC] User {user_id} not in model mapping. Using Category Fallback.")
            return self._get_category_fallback(user_id, top_n)

        rec_ids: List[int] = []
        try:
            # 2. ALS 모델 추천 실행 (N=top_n * 5: 후처리를 위한 충분한 풀 확보)
            recommended_idx_scores: List[Tuple[int, float]] = self._model.recommend(
                userid=user_index,
                user_items=self._user_items_matrix,
                N=top_n * 5,
                filter_already_liked_items=True,
                recalculate_user=True,
            )

            # 3. 후처리 (Reranking) 적용
            final_ranked_ids: List[int] = self._get_post_processed_ranking(user_id, recommended_idx_scores)
            rec_ids = final_ranked_ids[:top_n]

        except Exception as e:
            logger.error(
                f"[REC] ALS recommendation failed for user {user_id}: {e}",
                exc_info=True,
            )
            # ALS 실패 시 인기 강의 폴백
            return self._get_popular_lectures(top_n)

        # 4. 결과 부족 시 폴백 (보충)
        if len(rec_ids) < top_n:
            needed_count: int = top_n - len(rec_ids)
            logger.info(
                f"[REC] ALS only returned {len(rec_ids)} results. Filling {needed_count} with Category Fallback."
            )

            # 카테고리 폴백에서 필요한 수만큼만 가져와서 기존 결과에 추가
            fallback_qs: LectureQuerySet = self._get_category_fallback(user_id, needed_count)
            fallback_ids: List[int] = list(fallback_qs.values_list("id", flat=True))

            for lec_id in fallback_ids:
                if lec_id not in rec_ids:
                    rec_ids.append(lec_id)
                    if len(rec_ids) == top_n:
                        break

        # 5. 최종 쿼리셋 반환 (Query Prefetch 및 순서 유지)
        if not rec_ids:
            return CrawledLecture.objects.none()

        # ALS Reranking 결과는 순서가 중요하므로 Case/When으로 순서 유지
        qs: LectureQuerySet = (
            CrawledLecture.objects.filter(id__in=rec_ids)
            .order_by(
                Case(
                    *[When(id=id_, then=Value(i)) for i, id_ in enumerate(rec_ids)],
                    output_field=IntegerField(),
                )
            )
            .prefetch_related("lecturecategory_set__category")  # 카테고리 정보 프리패치
        )

        # 6. 추천 결과 로깅 (A/B 평가용)
        logger.info(f"[RECOMMENDATION_RESULT][{user_id}] IDs: {rec_ids}")

        return qs
