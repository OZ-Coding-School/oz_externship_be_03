import json
import logging
import random
import time
from collections import defaultdict
from datetime import datetime
from random import sample
from typing import Any, Dict, List, Optional, Set, Tuple, Union, cast

import joblib  # type: ignore
import numpy as np
from django.conf import settings
from django.core.cache import cache
from django.db.models import Avg, Case, FloatField, IntegerField, QuerySet, Value, When
from django.db.models.functions import Cast
from django_redis import get_redis_connection  # type: ignore
from implicit.als import AlternatingLeastSquares  # type: ignore
from scipy.sparse import csr_matrix

from apps.lecture.models import CrawledLecture, LectureCategory, UserPreferCategory
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

        self.redis_conn: Optional[RedisConnection] = self._get_redis_cache()
        self.redis_healthy: bool = self._check_redis_health(log_status=False)
        self.last_ping: float = time.time()

    def _get_redis_cache(self) -> Optional[RedisConnection]:
        try:
            # redis-py의 실제 연결 객체를 반환
            return get_redis_connection("default")
        except Exception as e:
            logger.error(f"[CACHE] Redis connection failed during init: {e}. Falling back to Django cache.")
            return None

    def _check_redis_health(self, log_status: bool = True) -> bool:
        if not self.redis_conn:
            return False
        previous_status = self.redis_healthy
        try:
            # ping() 호출은 성공 시 True 반환
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
            self._check_redis_health()
            self.last_ping = now
        return self.redis_healthy

    # ────────────────── 코드 중복 최소화: 캐시 헬퍼 함수 ──────────────────
    def _cache_get_safe(self, key: str, backend: str = "django") -> Optional[Any]:
        """캐시에서 joblib 직렬화된 데이터를 안전하게 읽고 역직렬화."""
        cached_raw = None
        try:
            if backend == "redis" and self._is_redis_ready() and self.redis_conn:
                cached_raw = self.redis_conn.get(key)
            elif backend == "django":
                cached_raw = cache.get(key)

            if cached_raw is None:
                return None

            # joblib.loads는 bytes 또는 file-like 객체를 기대함
            return joblib.loads(cached_raw)

        except Exception as e:
            logger.error(f"[CACHE_FAIL] {key} ({backend}) get/deserialization error: {e}. Invalidating cache.")
            if backend == "redis" and self._is_redis_ready() and self.redis_conn:
                self.redis_conn.delete(key)
            else:
                cache.delete(key)
            return None

    def _cache_set_safe(self, key: str, value: Any, timeout: int, backend: str = "django") -> None:
        """joblib 직렬화된 데이터를 캐시에 안전하게 발송."""
        if value is None:
            return
        try:
            # joblib.dumps는 bytes를 반환하며, redis와 django cache 모두 지원
            serialized_data = joblib.dumps(value, compress=3)
            if backend == "redis" and self._is_redis_ready() and self.redis_conn:
                self.redis_conn.set(key, serialized_data, ex=timeout)
            elif backend == "django":
                cache.set(key, serialized_data, timeout)
            # else: 캐시에 쓰지 않음
        except Exception as e:
            logger.error(f"[CACHE_FAIL] {key} ({backend}) serialization/set error: {e}")

    def _metadata_get_safe(self, cache_key: str) -> Optional[LectureMetadata]:
        """강의 메타데이터(JSON)를 캐시에서 읽고 역직렬화."""
        cached_raw = None
        try:
            if self._is_redis_ready() and self.redis_conn is not None:
                cached_raw = self.redis_conn.get(cache_key)
            else:
                cached_raw = cache.get(cache_key)

            if cached_raw is None:
                return None

            if isinstance(cached_raw, bytes):
                cached_raw = cached_raw.decode("utf-8")

            data = json.loads(cached_raw)
            return (float(data["rating"]), set(data["categories"]))

        except Exception as e:
            logger.warning(f"[META_CACHE] Cache retrieval failed for {cache_key}: {e}. Falling back to DB.")
            return None

    def _metadata_set_safe(self, cache_key: str, avg_rating: float, category_ids: Set[int]) -> None:
        """강의 메타데이터(JSON)를 캐시에 씁니다."""
        data_to_cache = {"rating": avg_rating, "categories": list(category_ids)}
        json_data = json.dumps(data_to_cache)
        try:
            if self._is_redis_ready() and self.redis_conn is not None:
                self.redis_conn.set(cache_key, json_data, ex=LECTURE_METADATA_TTL)
            else:
                cache.set(cache_key, json_data, LECTURE_METADATA_TTL)
        except Exception as e:
            logger.error(f"[META_CACHE] Error saving to cache for {cache_key}: {e}")

    # ──────────────────────────────────────────────────────────────────

    def _load_from_redis(self) -> bool:
        """캐시에서 ALS 모델 및 매핑 정보를 로드. (Redis 우선, Django Cache 폴백)"""

        # 1. Redis에서 로드 시도
        if self._is_redis_ready():
            cached_data = {k: self._cache_get_safe(k, backend="redis") for k in self.MODEL_CACHE_KEYS}
            if all(v is not None for v in cached_data.values()):
                self._apply_loaded_data(cached_data)
                logger.debug("[CACHE] Loaded model from Redis cache.")
                return True

        # 2. Django Cache에서 로드 시도
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
        # 캐시된 행렬 포맷이 coo든 csr이든 안전하게 csr로 변환하여 사용
        self._user_items_matrix = loaded_matrix.tocsr() if loaded_matrix else None

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
            # 행렬은 csr 포맷 그대로 저장 (joblib이 압축 처리)
            USER_ITEMS_MATRIX_CACHE_KEY: self._user_items_matrix,
        }

        # Redis와 Django 캐시에 동시에 저장
        for key, value in data_to_cache.items():
            self._cache_set_safe(key, value, MODEL_CACHE_TIMEOUT, backend="redis")
            self._cache_set_safe(key, value, MODEL_CACHE_TIMEOUT, backend="django")

    def _ensure_model_loaded(self) -> bool:
        """모델이 메모리에 로드되어 있는지 확인하고, 없으면 캐시/디스크에서 로드."""
        if self._model is not None:
            return True
        if self._load_from_redis():
            return True

        # 캐시 로드 실패 시 디스크 로드 시도 (Lock 기반 동시성 제어)
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

                    self._model = model
                    self._user_to_idx = u_to_i
                    self._lecture_to_idx = l_to_i
                    self._lecture_idx_to_id = {v: k for k, v in l_to_i.items()}
                    self._user_items_matrix = user_items_matrix
                    self._last_trained_at = last_trained_at

                    self._save_to_redis()
                    return True
                finally:
                    try:
                        cache.delete(ALS_TRAINING_LOCK_KEY)
                    except Exception as e:
                        logger.error(f"[CACHE_FAIL] Failed to release training lock: {e}")
            else:
                backoff_time = min(INITIAL_BACKOFF_SECONDS * (2**attempt), 30)
                jittered_time = backoff_time * (0.5 + random.random() * 0.5)
                if settings.DEBUG:
                    logger.debug(
                        f"[CACHE] Training lock active. Retrying in {jittered_time:.2f}s (Attempt {attempt + 1})."
                    )
                time.sleep(jittered_time)
        logger.error("[CACHE] Failed to acquire model load lock after multiple retries.")
        return False

    def _get_lecture_metadata_cached(self, lecture_id: int) -> LectureMetadata:
        """단일 강의의 메타데이터를 캐시 우선 로드."""
        cache_key = LECTURE_METADATA_CACHE_KEY.format(lecture_id)

        # 1. 캐시에서 로드 시도
        cached_metadata = self._metadata_get_safe(cache_key)
        if cached_metadata:
            return cached_metadata

        # 2. DB에서 로드 및 캐싱
        try:
            lecture_data = (
                CrawledLecture.objects.filter(id=lecture_id)
                .annotate(avg_rating_calculated=Avg(Cast("reviews__rating", output_field=FloatField())))
                .values("average_rating", "avg_rating_calculated")
                .first()
            )
            avg_rating_field = lecture_data.get("average_rating") if lecture_data else None
            if avg_rating_field is None:
                avg_rating_field = lecture_data.get("avg_rating_calculated") if lecture_data else None

            avg_rating = float(avg_rating_field) if avg_rating_field is not None else 0.0

            category_ids = set(
                LectureCategory.objects.filter(lecture_id=lecture_id).values_list("category_id", flat=True)
            )

            self._metadata_set_safe(cache_key, avg_rating, category_ids)
            return (avg_rating, category_ids)

        except Exception as e:
            logger.error(f"[METADATA] Failed to load metadata for lecture {lecture_id}: {e}")
            return (0.0, set())

    def _get_lectures_metadata_bulk(self, lecture_ids: List[int]) -> LectureMetadataMap:
        """여러 강의의 메타데이터를 캐시/DB에서 일괄 로드합니다."""
        metadata_map: LectureMetadataMap = {}
        cache_keys = [LECTURE_METADATA_CACHE_KEY.format(id) for id in lecture_ids]

        # 1. Bulk Cache 로드 시도
        try:
            cached_data = cache.get_many(cache_keys)
            hit_lecture_ids = set()
            cache_hit_count = 0

            for i, key in enumerate(cache_keys):
                if cached_data.get(key) is not None:
                    lec_id = lecture_ids[i]
                    metadata = self._deserialize_metadata(cached_data[key])
                    metadata_map[lec_id] = metadata
                    hit_lecture_ids.add(lec_id)
                    cache_hit_count += 1

            miss_lecture_ids = [id for id in lecture_ids if id not in hit_lecture_ids]

        except Exception as e:
            logger.warning(f"[META_CACHE] Bulk cache retrieval failed: {e}. Falling back all to DB.")
            miss_lecture_ids = lecture_ids

        # 2. DB에서 로드 및 캐싱
        if miss_lecture_ids:
            # 강의-평점 정보 로드
            lectures_ratings_qs = (
                CrawledLecture.objects.filter(id__in=miss_lecture_ids)
                .annotate(avg_rating_calculated=Avg(Cast("reviews__rating", output_field=FloatField())))
                .values("id", "average_rating", "avg_rating_calculated")
            )
            ratings_map: Dict[int, float] = {}
            for row in lectures_ratings_qs:
                lec_id = row["id"]
                avg_rating_field = row.get("average_rating")
                if avg_rating_field is None:
                    avg_rating_field = row.get("avg_rating_calculated")
                ratings_map[lec_id] = float(avg_rating_field) if avg_rating_field is not None else 0.0

            # 강의-카테고리 정보 로드
            categories_qs = LectureCategory.objects.filter(lecture_id__in=miss_lecture_ids).values_list(
                "lecture_id", "category_id"
            )
            categories_map: Dict[int, Set[int]] = defaultdict(set)
            for lec_id, cat_id in categories_qs:
                categories_map[lec_id].add(cat_id)

            cache_to_set = {}
            for lec_id in miss_lecture_ids:
                avg_rating = ratings_map.get(lec_id, 0.0)
                category_ids = categories_map.get(lec_id, set())

                metadata_map[lec_id] = (avg_rating, category_ids)

                # 캐시 저장을 위한 직렬화
                cache_key = LECTURE_METADATA_CACHE_KEY.format(lec_id)
                data_to_cache = {"rating": avg_rating, "categories": list(category_ids)}
                cache_to_set[cache_key] = json.dumps(data_to_cache)

            try:
                # Cache set_many는 Redis와 Django Cache 모두 지원
                cache.set_many(cache_to_set, LECTURE_METADATA_TTL)
            except Exception as e:
                logger.error(f"[META_CACHE] Error saving bulk cache: {e}")

        # 3. 누락된 ID에 기본값 설정
        for lec_id in lecture_ids:
            if lec_id not in metadata_map:
                metadata_map[lec_id] = (0.0, set())
        return metadata_map

    def _deserialize_metadata(self, raw_data: Union[bytes, str]) -> LectureMetadata:
        """강의 메타데이터 JSON 역직렬화 헬퍼."""
        if isinstance(raw_data, bytes):
            raw_data = raw_data.decode("utf-8")
        data = json.loads(raw_data)
        return (float(data["rating"]), set(data["categories"]))

    def _get_post_processed_ranking(self, user_id: int, recommended_with_score: List[Tuple[int, float]]) -> List[int]:
        if not recommended_with_score or self._lecture_idx_to_id is None:
            logger.error("[RERANK] Components missing or no recommendation. Skipping Reranking.")
            return []
        lecture_indices = [idx for idx, _ in recommended_with_score]
        lecture_ids = [self._lecture_idx_to_id[idx] for idx in lecture_indices]
        metadata_map = self._get_lectures_metadata_bulk(lecture_ids)
        user_prefer_cats = set(UserPreferCategory.objects.filter(user_id=user_id).values_list("category_id", flat=True))
        final_scores = []
        als_scores = np.array([s for _, s in recommended_with_score], dtype=np.float32)
        if als_scores.size > 0:
            processed_als_scores = np.power(als_scores, ALS_SCORE_POWER_DECAY)
            if NORMALIZE_ALS_SCORE:
                min_s, max_s = processed_als_scores.min(), processed_als_scores.max()
                ptp_score = max_s - min_s
                if ptp_score > 1e-6:
                    normalized_als_scores = (processed_als_scores - min_s) / ptp_score
                else:
                    logger.warning(
                        "[RERANK] ALS scores Min=Max (%s after decay). Setting normalized scores to 0.", f"{min_s:.3f}"
                    )
                    normalized_als_scores = processed_als_scores * 0
            else:
                normalized_als_scores = processed_als_scores
        else:
            normalized_als_scores = np.array([])
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

    def _get_popular_lectures(self, top_n: int) -> LectureQuerySet:
        cached_ids = cache.get(POPULAR_LECTURE_CACHE_KEY)
        if cached_ids:
            popular_ids = cached_ids[:top_n]
        else:
            try:
                popular_qs = CrawledLecture.objects.all().order_by(POPULAR_LECTURE_ORDER_BY)[: top_n * 2]
                all_ids = list(popular_qs.values_list("id", flat=True))
                if all_ids:
                    cache.set(POPULAR_LECTURE_CACHE_KEY, all_ids, POPULAR_LECTURE_TTL)
                    popular_ids = all_ids[:top_n]
                else:
                    popular_ids = []
            except Exception as e:
                logger.error(f"[FALLBACK] Error fetching popular lectures from DB: {e}")
                # 안전을 위해 ID 내림차순 (최신) fallback
                popular_ids = list(CrawledLecture.objects.all().order_by("-id").values_list("id", flat=True)[:top_n])
        if not popular_ids:
            return CrawledLecture.objects.none()
        return (
            CrawledLecture.objects.filter(id__in=popular_ids)
            .order_by(
                Case(*[When(id=id_, then=Value(i)) for i, id_ in enumerate(popular_ids)], output_field=IntegerField())
            )
            .prefetch_related("lecturecategory_set__category")
        )

    def _get_category_fallback(self, user_id: int, top_n: int) -> LectureQuerySet:
        user_prefer_cats = set(UserPreferCategory.objects.filter(user_id=user_id).values_list("category_id", flat=True))
        if not user_prefer_cats:
            logger.info(f"[COLD_START] User {user_id} has no preferred categories. Using Popular Fallback.")
            return self._get_popular_lectures(top_n)
        filtered_qs = (
            CrawledLecture.objects.filter(lecture_categories__category_id__in=user_prefer_cats)
            .distinct()
            .order_by(POPULAR_LECTURE_ORDER_BY)
        )
        try:
            # 2배수 로드 후 무작위 샘플링하여 다양성 확보
            ids = list(filtered_qs.values_list("id", flat=True)[: top_n * 2])
            if not ids:
                return self._get_popular_lectures(top_n)
            random_ids = sample(ids, min(top_n, len(ids)))
            return (
                CrawledLecture.objects.filter(id__in=random_ids)
                .order_by(
                    Case(
                        *[When(id=id_, then=Value(i)) for i, id_ in enumerate(random_ids)], output_field=IntegerField()
                    )
                )
                .prefetch_related("lecturecategory_set__category")
            )
        except Exception as e:
            logger.error(f"[FALLBACK] Error fetching category fallback using random.sample: {e}")
            return filtered_qs[:top_n]

    def recommend_lectures(self, user_id: int, top_n: int = 10) -> LectureQuerySet:
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
                N=top_n * 5,  # 충분한 양을 추천받아 후처리
                filter_already_liked_items=True,
                recalculate_user=True,
            )
            final_ranked_ids = self._get_post_processed_ranking(user_id, recommended_idx_scores)
            rec_ids = final_ranked_ids[:top_n]
        except Exception as e:
            logger.error(f"[REC] ALS recommendation failed for user {user_id}: {e}", exc_info=True)
            return self._get_popular_lectures(top_n)
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
            .prefetch_related("lecturecategory_set__category")
        )
        logger.info(f"[RECOMMENDATION_RESULT][{user_id}] IDs: {rec_ids}")
        return qs
