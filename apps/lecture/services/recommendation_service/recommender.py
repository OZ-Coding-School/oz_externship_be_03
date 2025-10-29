import logging
import pickle
import time
from collections import defaultdict
from datetime import datetime
from random import sample
from typing import Any, Dict, List, Optional, Set, Tuple, Union, cast

import joblib  # type: ignore
import numpy as np
from django.conf import settings
from django.core.cache import cache
from django.db.models import Case, IntegerField, QuerySet, Value, When
from django.utils import timezone
from django_redis import get_redis_connection  # type: ignore
from implicit.als import AlternatingLeastSquares  # type: ignore
from scipy.sparse import csr_matrix

from apps.lecture.models import (
    CrawledLecture,
    LectureBookmark,
    LectureCategory,
    UserPreferCategory,
)
from apps.lecture.services.recommendation_service.constants import (
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
    POPULAR_LECTURE_CACHE_KEY,
    POPULAR_LECTURE_ORDER_BY,
    POPULAR_LECTURE_TTL,
    REVIEW_RATING_MULTIPLIER,
    U_TO_IDX_CACHE_KEY,
    USER_ITEMS_MATRIX_CACHE_KEY,
)
from apps.lecture.services.recommendation_service.data_loader import DataLoader
from apps.lecture.services.recommendation_service.model_trainer import (
    ModelBundleReturn,
    ModelTrainer,
)

logger = logging.getLogger(__name__)

LectureQuerySet = QuerySet[CrawledLecture]
LectureMetadata = Tuple[float, Set[int]]
LectureMetadataMap = Dict[int, LectureMetadata]
RedisConnection = Any


class RecommendationService:
    REDIS_PING_INTERVAL_SECONDS = 60 * 60
    MODEL_CACHE_KEYS: List[str] = [
        ALS_MODEL_CACHE_KEY,
        U_TO_IDX_CACHE_KEY,
        L_TO_IDX_CACHE_KEY,
        L_IDX_TO_ID_CACHE_KEY,
        USER_ITEMS_MATRIX_CACHE_KEY,
    ]

    def __init__(self) -> None:
        self.data_loader = DataLoader()
        self.model_trainer = ModelTrainer(self.data_loader)

        self._model: Optional[AlternatingLeastSquares] = None
        self._user_to_idx: Optional[Dict[int, int]] = None
        self._lecture_to_idx: Optional[Dict[int, int]] = None
        self._lecture_idx_to_id: Optional[Dict[int, int]] = None
        self._user_items_matrix: Optional[csr_matrix] = None
        self._last_trained_at: Optional[datetime] = None
        self.redis_healthy = False
        self.redis_conn: Optional[RedisConnection] = self._get_redis_cache()
        self.redis_healthy = self._check_redis_health(log_status=False)
        self.last_ping: float = time.time()

    def _get_redis_cache(self) -> Optional[RedisConnection]:
        try:
            return get_redis_connection("default")
        except Exception as e:
            logger.error(f"[CACHE] Redis connection failed during init: {e}. Falling back to Django cache.")
            return None

    def _check_redis_health(self, log_status: bool = True) -> bool:
        if not self.redis_conn:
            return False
        previous_status = self.redis_healthy
        try:
            new_status: bool = bool(self.redis_conn.ping())
            self.redis_healthy = new_status
            if not previous_status and new_status:
                logger.info("[CACHE] Redis connection recovered.")
            elif previous_status and not new_status and log_status:
                logger.warning("[CACHE] Redis PING failed, connection unstable. Falling back to Django cache.")
            return new_status
        except Exception as e:
            self.redis_healthy = False
            if previous_status and log_status:
                logger.warning(f"[CACHE] Redis connection error during PING: {e}. Falling back to Django cache.")
            return False

    def _is_redis_ready(self) -> bool:
        now = time.time()
        if self.redis_healthy and (now - self.last_ping < self.REDIS_PING_INTERVAL_SECONDS):
            return True
        status_check_interval = 60 if not self.redis_healthy else self.REDIS_PING_INTERVAL_SECONDS
        if now - self.last_ping >= status_check_interval:
            self._check_redis_health(log_status=False)  # 불필요한 로그 출력 방지
            self.last_ping = now
        return self.redis_healthy

    def _cache_get_safe(self, key: str, backend: str = "django") -> Optional[Any]:
        """캐시에서 pickle 직렬화된 데이터를 안전하게 읽고 역직렬화."""
        cached_raw = None
        try:
            if backend == "redis" and self._is_redis_ready() and self.redis_conn:
                cached_raw = self.redis_conn.get(key)
            elif backend == "django":
                cached_raw = cache.get(key)

            if cached_raw is None:
                return None

            return pickle.loads(cached_raw)

        except Exception as e:
            logger.error(f"[CACHE_FAIL] {key} ({backend}) get/deserialization error: {e}. Invalidating cache.")
            if backend == "redis" and self._is_redis_ready() and self.redis_conn:
                self.redis_conn.delete(key)
            else:
                cache.delete(key)
            return None

    def _cache_set_safe(self, key: str, value: Any, timeout: int, backend: str = "django") -> None:
        """pickle 직렬화된 데이터를 캐시에 안전하게 저장."""
        if value is None:
            return
        try:
            serialized_data = pickle.dumps(value, pickle.HIGHEST_PROTOCOL)
            if backend == "redis" and self._is_redis_ready() and self.redis_conn:
                self.redis_conn.set(key, serialized_data, ex=timeout)
            elif backend == "django":
                cache.set(key, serialized_data, timeout)
        except Exception as e:
            logger.error(f"[CACHE_FAIL] {key} ({backend}) serialization/set error: {e}")

    def _metadata_get_safe(self, cache_key: str) -> Optional[LectureMetadata]:
        """강의 메타데이터를 캐시에서 읽고 역직렬화 (pickle 사용으로 통일)."""
        return self._cache_get_safe(cache_key, backend="redis" if self._is_redis_ready() else "django")

    def _metadata_set_safe(self, cache_key: str, avg_rating: float, category_ids: Set[int]) -> None:
        """강의 메타데이터를 캐시에 저장 (pickle 사용으로 통일)."""
        metadata: LectureMetadata = (avg_rating, category_ids)
        self._cache_set_safe(
            cache_key, metadata, LECTURE_METADATA_TTL, backend="redis" if self._is_redis_ready() else "django"
        )

    def _load_from_redis(self) -> bool:
        """캐시에서 ALS 모델 및 매핑 정보를 로드. (Redis 우선, Django Cache 폴백)"""
        if self._is_redis_ready():
            cached_data = {k: self._cache_get_safe(k, backend="redis") for k in self.MODEL_CACHE_KEYS}
            if all(v is not None for v in cached_data.values()):
                self._apply_loaded_data(cached_data)
                logger.debug("[CACHE] Loaded model from Redis cache.")
                return True

        cached_data = {k: self._cache_get_safe(k, backend="django") for k in self.MODEL_CACHE_KEYS}
        if all(v is not None for v in cached_data.values()):
            self._apply_loaded_data(cached_data)
            logger.debug("[CACHE] Loaded model from Django cache.")
            return True

        logger.warning("[CACHE] No cache data found in Redis or Django cache.")
        return False

    def _apply_loaded_data(self, cached_data: Dict[str, Any]) -> None:
        """로드된 캐시 데이터를 인스턴스 변수에 적용."""
        self._model = cached_data[ALS_MODEL_CACHE_KEY]
        self._user_to_idx = cached_data[U_TO_IDX_CACHE_KEY]
        self._lecture_to_idx = cached_data[L_TO_IDX_CACHE_KEY]
        self._lecture_idx_to_id = cached_data[L_IDX_TO_ID_CACHE_KEY]
        loaded_matrix = cached_data[USER_ITEMS_MATRIX_CACHE_KEY]
        self._user_items_matrix = loaded_matrix.tocsr() if loaded_matrix is not None else None

    def _save_to_redis(self) -> None:
        """인스턴스 모델 데이터를 캐시에 저장. (Redis/Django Cache)"""
        is_ready = (
            self._model is not None
            and self._user_to_idx is not None
            and self._lecture_to_idx is not None
            and self._lecture_idx_to_id is not None
            and self._user_items_matrix is not None
            and self._user_items_matrix.size > 0
        )
        if not is_ready:
            return

        data_to_cache: Dict[str, Any] = {
            ALS_MODEL_CACHE_KEY: self._model,
            U_TO_IDX_CACHE_KEY: self._user_to_idx,
            L_TO_IDX_CACHE_KEY: self._lecture_to_idx,
            L_IDX_TO_ID_CACHE_KEY: self._lecture_idx_to_id,
            USER_ITEMS_MATRIX_CACHE_KEY: self._user_items_matrix,
        }

        for key, value in data_to_cache.items():
            self._cache_set_safe(key, value, MODEL_CACHE_TIMEOUT, backend="redis")
            self._cache_set_safe(key, value, MODEL_CACHE_TIMEOUT, backend="django")

    def _ensure_model_loaded(self) -> bool:
        """모델이 메모리에 로드되어 있는지 확인하고, 없으면 캐시/디스크에서 로드."""
        if self._model is not None:
            return True
        if self._load_from_redis():
            return True

        for attempt in range(MAX_CACHE_LOAD_RETRIES):
            if cache.add(ALS_TRAINING_LOCK_KEY, True, timeout=300):
                try:
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

                    if (
                        model is None
                        or u_to_i is None
                        or l_to_i is None
                        or user_items_matrix is None
                        or last_trained_at is None
                    ):
                        logger.error("[FILE] Essential model components missing from disk.")
                        return False

                    # Timezone-aware 변환 추가
                    if last_trained_at.tzinfo is None:
                        last_trained_at = timezone.make_aware(last_trained_at)

                    self._model = model
                    self._user_to_idx = u_to_i
                    self._lecture_to_idx = l_to_i
                    self._lecture_idx_to_id = {v: k for k, v in l_to_i.items()}
                    self._user_items_matrix = user_items_matrix
                    self._last_trained_at = last_trained_at

                    self._save_to_redis()
                    return True

                except Exception as e:
                    logger.error(f"[FILE] Error loading model from disk: {e}", exc_info=True)
                    return False
                finally:
                    cache.delete(ALS_TRAINING_LOCK_KEY)
            else:
                backoff = INITIAL_BACKOFF_SECONDS * (2**attempt)
                logger.info(f"[LOCK] Model load locked. Retry {attempt + 1}/{MAX_CACHE_LOAD_RETRIES} after {backoff}s")
                time.sleep(backoff)

        logger.error("[LOCK] Failed to acquire lock for model loading after retries.")
        return False

    def _get_lectures_metadata_bulk(self, lecture_ids: List[int]) -> LectureMetadataMap:
        """강의 메타데이터 일괄 조회 (캐시 우선, DB 폴백) - Redis pipeline 최적화"""
        metadata_map: LectureMetadataMap = {}
        miss_lecture_ids: List[int] = []

        # Redis pipeline을 사용한 일괄 조회 (성능 최적화)
        if self._is_redis_ready() and self.redis_conn:
            try:
                pipeline = self.redis_conn.pipeline()
                cache_keys = [LECTURE_METADATA_CACHE_KEY.format(lec_id) for lec_id in lecture_ids]

                for cache_key in cache_keys:
                    pipeline.get(cache_key)

                cached_results = pipeline.execute()

                for lec_id, cached_raw in zip(lecture_ids, cached_results):
                    if cached_raw is not None:
                        try:
                            metadata_map[lec_id] = pickle.loads(cached_raw)
                        except Exception as e:
                            logger.warning(f"[CACHE] Failed to deserialize metadata for lecture {lec_id}: {e}")
                            miss_lecture_ids.append(lec_id)
                    else:
                        miss_lecture_ids.append(lec_id)
            except Exception as e:
                logger.warning(f"[CACHE] Redis pipeline failed: {e}. Falling back to individual queries.")
                miss_lecture_ids = lecture_ids
        else:
            # Redis 사용 불가 시 개별 캐시 조회
            for lec_id in lecture_ids:
                cache_key = LECTURE_METADATA_CACHE_KEY.format(lec_id)
                cached_metadata = self._metadata_get_safe(cache_key)
                if cached_metadata is not None:
                    metadata_map[lec_id] = cached_metadata
                else:
                    miss_lecture_ids.append(lec_id)

        # 캐시 미스 항목 DB 조회
        if miss_lecture_ids:
            ratings_qs = CrawledLecture.objects.filter(id__in=miss_lecture_ids).values("id", "average_rating")
            ratings_map: Dict[int, float] = {
                r["id"]: float(r["average_rating"]) for r in ratings_qs if r["average_rating"] is not None
            }

            categories_qs = LectureCategory.objects.filter(lecture_id__in=miss_lecture_ids).values_list(
                "lecture_id", "category_id"
            )
            categories_map: Dict[int, Set[int]] = defaultdict(set)
            for lec_id, cat_id in categories_qs:
                categories_map[lec_id].add(cat_id)

            for lec_id in miss_lecture_ids:
                avg_rating = ratings_map.get(lec_id, 0.0)
                category_ids = categories_map.get(lec_id, set())
                metadata_map[lec_id] = (avg_rating, category_ids)

                # 캐시에 저장
                cache_key = LECTURE_METADATA_CACHE_KEY.format(lec_id)
                self._metadata_set_safe(cache_key, avg_rating, category_ids)

        return metadata_map

    def _get_post_processed_ranking(self, user_id: int, recommended_idx_scores: List[Tuple[int, float]]) -> List[int]:
        """ALS 추천 결과에 평점/카테고리 보너스 적용 후 재정렬"""
        if not recommended_idx_scores:
            return []

        lecture_indices, als_scores = zip(*recommended_idx_scores)
        lecture_ids = [cast(Dict[int, int], self._lecture_idx_to_id)[idx] for idx in lecture_indices]

        metadata_map: LectureMetadataMap = self._get_lectures_metadata_bulk(lecture_ids)
        user_prefer_cats: Set[int] = set(
            UserPreferCategory.objects.filter(user_id=user_id).values_list("category_id", flat=True)
        )

        als_scores_array = np.array(als_scores, dtype=np.float32)
        processed_als_scores = np.power(als_scores_array, ALS_SCORE_POWER_DECAY)

        if NORMALIZE_ALS_SCORE and processed_als_scores.size > 0:
            min_s = processed_als_scores.min()
            max_s = processed_als_scores.max()
            if max_s > min_s:
                normalized_als_scores = (processed_als_scores - min_s) / (max_s - min_s)
            else:
                if settings.DEBUG:
                    logger.debug(
                        "[RECSCORE] All ALS scores identical (%s after decay). Setting normalized scores to 0.",
                        f"{min_s:.3f}",
                    )
                normalized_als_scores = processed_als_scores * 0
        else:
            normalized_als_scores = np.array([])

        final_scores: List[Tuple[int, float]] = []
        for i, lec_id in enumerate(lecture_ids):
            avg_rating, lec_cats = metadata_map.get(lec_id, (0.0, set()))
            final_als_score = (
                normalized_als_scores[i] if normalized_als_scores.size > 0 and i < normalized_als_scores.size else 0.0
            )
            normalized_rating = avg_rating / 5.0
            rating_bonus = normalized_rating * REVIEW_RATING_MULTIPLIER
            matched_cats = user_prefer_cats.intersection(lec_cats)
            category_bonus = len(matched_cats) * CATEGORY_MATCH_BONUS
            final_score = final_als_score + rating_bonus + category_bonus
            final_scores.append((lec_id, final_score))

            if settings.DEBUG:
                logger.debug(
                    "[RECSCORE][U:%s] L:%s: ALS_Final(%.3f) + R(%.3f) + C(%.3f) -> Final(%.3f)",
                    user_id,
                    lec_id,
                    final_als_score,
                    rating_bonus,
                    category_bonus,
                    final_score,
                )

        final_scores.sort(key=lambda x: x[1], reverse=True)
        return [lec_id for lec_id, _ in final_scores]

    def _get_popular_lectures(self, user_id: int, top_n: int) -> LectureQuerySet:
        """인기 강의 조회 (북마크 제외, 캐시 활용)"""
        bookmarked_ids = list(LectureBookmark.objects.filter(user_id=user_id).values_list("lecture_id", flat=True))

        cached_ids = cache.get(POPULAR_LECTURE_CACHE_KEY)

        if cached_ids:
            filtered_ids = [id_ for id_ in cached_ids if id_ not in bookmarked_ids]
            popular_ids = filtered_ids[:top_n]
        else:
            try:
                # 캐시용 쿼리 한 번만 실행 (북마크 필터링 없음)
                unfiltered_all_ids = list(
                    CrawledLecture.objects.all()
                    .order_by(POPULAR_LECTURE_ORDER_BY)[: top_n * 2]
                    .values_list("id", flat=True)
                )

                if unfiltered_all_ids:
                    cache.set(POPULAR_LECTURE_CACHE_KEY, unfiltered_all_ids, POPULAR_LECTURE_TTL)

                # 북마크 필터링은 메모리에서 처리
                popular_ids = [id_ for id_ in unfiltered_all_ids if id_ not in bookmarked_ids][:top_n]

            except Exception as e:
                logger.error(f"[FALLBACK] Error fetching popular lectures from DB: {e}")
                # 안전을 위해 ID 내림차순 (최신) fallback
                popular_ids = list(
                    CrawledLecture.objects.all()
                    .exclude(id__in=bookmarked_ids)
                    .order_by("-id")
                    .values_list("id", flat=True)[:top_n]
                )

        if not popular_ids:
            return CrawledLecture.objects.none()

        return (
            CrawledLecture.objects.filter(id__in=popular_ids)
            .order_by(
                Case(*[When(id=id_, then=Value(i)) for i, id_ in enumerate(popular_ids)], output_field=IntegerField())
            )
            .prefetch_related("lecture_categories__category")
        )

    def _get_category_fallback(self, user_id: int, top_n: int) -> LectureQuerySet:
        """선호 카테고리 기반 강의 조회 (북마크 제외)"""
        bookmarked_ids = list(LectureBookmark.objects.filter(user_id=user_id).values_list("lecture_id", flat=True))

        user_prefer_cats = set(UserPreferCategory.objects.filter(user_id=user_id).values_list("category_id", flat=True))

        if not user_prefer_cats:
            logger.info(f"[COLD_START] User {user_id} has no preferred categories. Using Popular Fallback.")
            return self._get_popular_lectures(user_id, top_n)

        filtered_qs = (
            CrawledLecture.objects.filter(lecture_categories__category_id__in=user_prefer_cats)
            .exclude(id__in=bookmarked_ids)
            .distinct()
            .order_by(POPULAR_LECTURE_ORDER_BY)
        )

        try:
            ids = list(filtered_qs.values_list("id", flat=True)[: top_n * 2])

            if not ids:
                return self._get_popular_lectures(user_id, top_n)

            random_ids = sample(ids, min(top_n, len(ids)))

            return (
                CrawledLecture.objects.filter(id__in=random_ids)
                .order_by(
                    Case(
                        *[When(id=id_, then=Value(i)) for i, id_ in enumerate(random_ids)], output_field=IntegerField()
                    )
                )
                .prefetch_related("lecture_categories__category")
            )
        except Exception as e:
            logger.error(f"[FALLBACK] Error fetching category fallback using random.sample: {e}")
            return filtered_qs[:top_n]

    def recommend_lectures(self, user_id: int, top_n: int = 10) -> LectureQuerySet:
        """사용자 맞춤 강의 추천 (ALS → Category Fallback → Popular Fallback)"""
        if not self._ensure_model_loaded() or self._model is None or self._user_items_matrix is None:
            logger.warning(f"[REC] Model not available for user {user_id}. Using Category Fallback.")
            return self._get_category_fallback(user_id, top_n)

        user_index = cast(Dict[int, int], self._user_to_idx).get(user_id)

        if user_index is None:
            logger.warning(f"[REC] User {user_id} not in model mapping. Using Category Fallback.")
            return self._get_category_fallback(user_id, top_n)

        rec_ids = []
        try:
            recommended_idx_scores = self._model.recommend(
                userid=user_index,
                user_items=self._user_items_matrix,
                N=top_n * 5,
                filter_already_liked_items=True,
                recalculate_user=True,
            )
            final_ranked_ids = self._get_post_processed_ranking(user_id, recommended_idx_scores)
            rec_ids = final_ranked_ids[:top_n]
        except Exception as e:
            logger.error(f"[REC] ALS recommendation failed for user {user_id}: {e}", exc_info=True)
            # ALS 실패 시: Category Fallback으로 통일
            return self._get_category_fallback(user_id, top_n)

        if len(rec_ids) < top_n:
            needed_count = top_n - len(rec_ids)
            logger.info(
                f"[REC] ALS only returned {len(rec_ids)} results. Filling {needed_count} with Category Fallback."
            )

            fallback_qs = self._get_category_fallback(user_id, needed_count)
            fallback_ids = list(fallback_qs.values_list("id", flat=True))

            for lec_id in fallback_ids:
                if lec_id not in rec_ids:
                    rec_ids.append(lec_id)
                    if len(rec_ids) == top_n:
                        break

        if not rec_ids:
            return CrawledLecture.objects.none()

        qs = (
            CrawledLecture.objects.filter(id__in=rec_ids)
            .order_by(
                Case(*[When(id=id_, then=Value(i)) for i, id_ in enumerate(rec_ids)], output_field=IntegerField())
            )
            .prefetch_related("lecture_categories__category")
        )
        logger.info(f"[RECOMMENDATION_RESULT][{user_id}] IDs: {rec_ids}")
        return qs
