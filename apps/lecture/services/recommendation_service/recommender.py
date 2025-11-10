import logging
import time
from collections import defaultdict
from datetime import datetime
from random import sample
from typing import Any, DefaultDict, Dict, List, Optional, Set, Tuple, cast

import numpy as np
from django.core.cache import cache
from django.db.models import QuerySet
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
from apps.users.models import User

logger = logging.getLogger(__name__)

LectureQuerySet = QuerySet[CrawledLecture]
LectureMetadata = Tuple[float, Set[int]]
LectureMetadataMap = Dict[int, LectureMetadata]
RedisConnection = Any


class RecommendationService:
    """
    ALS 기반 강의 추천 서비스 메인 클래스

    역할:
    - 사용자 맞춤 강의 추천 제공
    - 다단계 폴백 전략 (ALS → 카테고리 → 인기 강의)
    - 모델 및 메타데이터 캐싱 관리
    - Redis 헬스체크 및 자동 폴백

    캐싱 계층:
    1. 메모리: 인스턴스 변수 (_model, _user_to_idx 등)
    2. Redis: 빠른 분산 캐시 (우선 사용)
    3. Django 캐시: Redis 실패 시 폴백
    4. 디스크: 영구 저장소 (pickle 파일)

    추천 전략:
    1. ALS 모델 기반 추천 (협업 필터링)
    2. 사용자 선호 카테고리 기반 추천
    3. 전체 인기 강의 추천
    """

    # Redis 헬스체크 주기 (1시간)
    REDIS_PING_INTERVAL_SECONDS = 60 * 60
    # 캐시에 저장할 모델 관련 키 목록
    MODEL_CACHE_KEYS: List[str] = [
        ALS_MODEL_CACHE_KEY,  # ALS 모델 객체
        U_TO_IDX_CACHE_KEY,  # 사용자 ID → 행렬 인덱스 매핑
        L_TO_IDX_CACHE_KEY,  # 강의 ID → 행렬 인덱스 매핑
        L_IDX_TO_ID_CACHE_KEY,  # 행렬 인덱스 → 강의 ID 매핑
        USER_ITEMS_MATRIX_CACHE_KEY,  # 사용자-강의 상호작용 행렬
    ]

    def __init__(self) -> None:
        """RecommendationService 초기화 작업:
        1. DataLoader 및 ModelTrainer 인스턴스 생성
        2. 모델 관련 인스턴스 변수 초기화 (None)
        3. Redis 연결 설정 및 헬스체크
        """
        # 데이터 로더 및 모델 트레이너 초기화
        self.data_loader = DataLoader()
        self.model_trainer = ModelTrainer(self.data_loader)

        # 모델 관련 인스턴스 변수 (메모리 캐시)
        self._model: Optional[AlternatingLeastSquares] = None  # ALS 모델
        self._user_to_idx: Optional[Dict[int, int]] = None  # 사용자 ID → 인덱스
        self._lecture_to_idx: Optional[Dict[int, int]] = None  # 강의 ID → 인덱스
        self._lecture_idx_to_id: Optional[Dict[int, int]] = None  # 인덱스 → 강의 ID
        self._user_items_matrix: Optional[csr_matrix] = None  # 상호작용 행렬
        self._last_trained_at: Optional[datetime] = None  # 마지막 학습 시각

        # Redis 연결 상태 관리
        self.redis_healthy = False  # Redis 연결 상태 플래그
        self.redis_conn: Optional[RedisConnection] = self._get_redis_cache()  # Redis 연결 객체
        self.redis_healthy = self._check_redis_health(log_status=False)  # 초기 헬스체크
        self.last_ping: float = time.time()  # 마지막 PING 시각

    def _get_redis_cache(self) -> Optional[RedisConnection]:
        """
        Redis 연결 초기화

        Returns:
            Redis 연결 객체 또는 None (연결 실패 시)

        Note:
            - 연결 실패 시 에러 로그 출력 후 None 반환
            - None 반환 시 Django 캐시로 자동 폴백
        """
        try:
            return get_redis_connection("default")
        except Exception as e:
            logger.error(f"[CACHE] Redis connection failed during init: {e}. Falling back to Django cache.")
            return None

    def _check_redis_health(self, log_status: bool = True) -> bool:
        """
        Redis 연결 상태 확인 (PING 명령)

        Args:
            log_status: 상태 변경 시 로그 출력 여부

        Returns:
            Redis 연결 정상 여부 (True/False)

        처리 로직:
        1. Redis 연결 객체 존재 확인
        2. PING 명령 실행
        3. 상태 변경 시에만 로그 출력 (노이즈 감소)

        상태 변경 케이스:
        - 복구: previous_status=False, new_status=True → INFO 로그
        - 실패: previous_status=True, new_status=False → WARNING 로그
        """
        # Redis 연결 객체 없으면 즉시 False 반환
        if not self.redis_conn:
            return False
        # 이전 상태 저장 (상태 변경 감지용)
        previous_status = self.redis_healthy
        try:
            # PING 명령으로 연결 상태 확인
            new_status: bool = bool(self.redis_conn.ping())
            self.redis_healthy = new_status
            # 상태 변경 시 로그 출력
            if not previous_status and new_status:
                # 복구: 실패 → 성공
                logger.info("[CACHE] Redis connection recovered.")
            elif previous_status and not new_status and log_status:
                # 실패: 성공 → 실패
                logger.warning("[CACHE] Redis PING failed, connection unstable. Falling back to Django cache.")
            return new_status
        except Exception as e:
            # PING 실패 시 False 반환
            self.redis_healthy = False
            if previous_status and log_status:
                logger.warning(f"[CACHE] Redis connection error during PING: {e}. Falling back to Django cache.")
            return False

    def _is_redis_ready(self) -> bool:
        """
        Redis 사용 가능 여부 확인 (주기적 헬스체크 포함)

        Returns:
            Redis 사용 가능 여부 (True/False)

        처리 로직:
        1. 최근 PING 성공 + 1시간 미경과 → 즉시 True 반환
        2. 일정 시간 경과 시 헬스체크 재실행
        3. 연결 실패 상태에서는 60초마다 복구 시도

        헬스체크 주기:
        - 정상 상태: 1시간 (REDIS_PING_INTERVAL_SECONDS)
        - 실패 상태: 60초
        """
        now = time.time()
        # 최근 PING 성공 + 1시간 미경과 → 즉시 True
        if self.redis_healthy and (now - self.last_ping < self.REDIS_PING_INTERVAL_SECONDS):
            return True
        # 헬스체크 주기 결정 (실패 상태: 60초, 정상 상태: 1시간)
        status_check_interval = 60 if not self.redis_healthy else self.REDIS_PING_INTERVAL_SECONDS
        # 주기 경과 시 헬스체크 재실행
        if now - self.last_ping >= status_check_interval:
            self.last_ping = now
            self._check_redis_health()
        return self.redis_healthy

    def _cache_get_safe(self, key: str) -> Any:
        """
        캐시에서 데이터를 안전하게 읽기 (Django 캐시의 자동 pickle 처리 활용)

        Args:
            key: 캐시 키
            backend: 캐시 백엔드 ('redis' 또는 'django')

        Returns:
            역직렬화된 데이터 또는 None (실패 시)

        처리 흐름:
        1. 지정된 백엔드에서 데이터 조회
        2. Django 캐시가 자동으로 pickle 역직렬화 처리
        3. 실패 시 캐시 무효화 (데이터 손상 방지)

        Note:
            - Redis 백엔드는 연결 상태 확인 후 사용
            - Django Redis 백엔드가 자동으로 pickle 처리하므로 중복 직렬화 제거
            - 예외 발생 시 None 반환 (프로세스 계속)
        """
        try:
            # Django 캐시가 자동으로 pickle 처리
            cached_data = cache.get(key)
            return cached_data

        except Exception as e:
            # 조회 실패 시 캐시 무효화
            logger.error(f"[CACHE_FAIL] {key} get error: {e}. Invalidating cache.")
            cache.delete(key)
            return None

    def _cache_set_safe(self, key: str, value: Any, timeout: int) -> None:
        """
        데이터를 캐시에 안전하게 저장 (Django 캐시의 자동 pickle 처리 활용)

        Args:
            key: 캐시 키
            value: 저장할 데이터
            timeout: TTL (초 단위)
            backend: 캐시 백엔드 ('redis' 또는 'django')

        처리 흐름:
        1. value가 None이면 즉시 반환 (저장 안 함)
        2. Django 캐시가 자동으로 pickle 직렬화 처리
        3. 백엔드별 저장 (Redis 또는 Django 캐시)

        Note:
            - Django Redis 백엔드가 자동으로 pickle 처리하므로 중복 직렬화 제거
            - 저장 실패 시 에러 로그만 출력
            - 예외 발생해도 프로세스 계속 진행
        """
        # None 값은 저장하지 않음
        if value is None:
            return
        try:
            # Django 캐시가 자동으로 pickle 처리
            cache.set(key, value, timeout)
        except Exception as e:
            # 저장 실패 시 에러 로그만 출력
            logger.error(f"[CACHE_FAIL] {key} set error: {e}")

    def _metadata_get_safe(self, cache_key: str) -> Optional[LectureMetadata]:
        """
        강의 메타데이터를 캐시에서 읽고 역직렬화

        Args:
            cache_key: 캐시 키

        Returns:
            (평점, 카테고리_ID_집합) 튜플 또는 None

        Note:
            - Django 캐시가 자동으로 pickle 처리
        """
        result = self._cache_get_safe(cache_key)
        return cast(Optional[LectureMetadata], result)

    def _metadata_set_safe(self, cache_key: str, avg_rating: float, category_ids: Set[int]) -> None:
        """
        강의 메타데이터를 캐시에 저장

        Args:
            cache_key: 캐시 키
            avg_rating: 평균 평점
            category_ids: 카테고리 ID 집합

        Note:
            - Django 캐시가 자동으로 pickle 처리
        """
        metadata: LectureMetadata = (avg_rating, category_ids)
        self._cache_set_safe(cache_key, metadata, LECTURE_METADATA_TTL)

    def _load_from_redis(self) -> bool:
        """
        캐시에서 ALS 모델 및 매핑 정보를 로드

        Returns:
            로드 성공 여부 (True/False)

        처리 흐름:
        1. Redis 연결 가능 시 Redis에서 로드 시도
        2. Redis 실패 시 Django 캐시에서 로드 시도
        3. 모든 캐시 키가 존재해야 성공
        4. 로드된 데이터를 인스턴스 변수에 적용

        Note:
            - 부분 로드는 실패로 간주 (일관성 보장)
        """
        cached_data = {k: self._cache_get_safe(k) for k in self.MODEL_CACHE_KEYS}

        if all(v is not None for v in cached_data.values()):
            self._apply_loaded_data(cached_data)
            logger.debug("[CACHE] Loaded model from cache.")
            return True

        logger.warning("[CACHE] No cache data found in cache.")
        return False

    def _apply_loaded_data(self, cached_data: Dict[str, Any]) -> None:
        """
        로드된 캐시 데이터를 인스턴스 변수에 적용

        Args:
            cached_data: 캐시에서 로드한 데이터 딕셔너리

        Note:
            - 모든 필수 키가 존재하는지 사전 검증 필요
            - 행렬은 CSR 형식으로 변환하여 저장
        """
        self._model = cached_data[ALS_MODEL_CACHE_KEY]
        self._user_to_idx = cached_data[U_TO_IDX_CACHE_KEY]
        self._lecture_to_idx = cached_data[L_TO_IDX_CACHE_KEY]
        self._lecture_idx_to_id = cached_data[L_IDX_TO_ID_CACHE_KEY]
        loaded_matrix = cached_data[USER_ITEMS_MATRIX_CACHE_KEY]
        self._user_items_matrix = loaded_matrix.tocsr() if loaded_matrix is not None else None

    def _save_to_redis(self) -> None:
        """
        인스턴스 모델 데이터를 캐시에 저장

        Note:
            - Redis 우선 저장. Redis 연결 실패 시 Django 캐시로 자동 폴백.
            - 모든 필수 데이터가 준비되어야 저장 시도
            - 저장 실패 시 에러 로그만 출력 (프로세스 계속)
        """
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
            self._cache_set_safe(key, value, MODEL_CACHE_TIMEOUT)

    def _ensure_model_loaded(self) -> bool:
        """
        모델이 메모리에 로드되어 있는지 확인하고, 없으면 캐시/디스크에서 로드

        Returns:
            모델 로드 성공 여부 (True/False)

        처리 흐름:
        1. 메모리에 모델 존재 확인
        2. 캐시에서 로드 시도
        3. 디스크에서 로드 시도 (락 기반 동시성 제어)
        4. 로드 실패 시 재시도 (exponential backoff)

        Note:
            - 최대 5회 재시도 (MAX_CACHE_LOAD_RETRIES)
            - 재시도 간격: 1초, 2초, 4초, 8초, 16초
            - 락 타임아웃: 300초
        """
        # 1. 메모리에 모델 존재 확인
        if self._model is not None:
            return True
        # 2. 캐시에서 로드 시도
        if self._load_from_redis():
            return True

        # 3. 디스크에서 로드 시도 (락 기반 동시성 제어)
        for attempt in range(MAX_CACHE_LOAD_RETRIES):
            # 락 획득 시도 (다른 프로세스가 로드 중이면 대기)
            if cache.add(ALS_TRAINING_LOCK_KEY, True, timeout=300):
                try:
                    # 디스크에서 모델 로드
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

                    # 필수 컴포넌트 검증
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
                    self._user_items_matrix = user_items_matrix.tocsr()
                    self._last_trained_at = last_trained_at

                    # 캐시에 저장
                    self._save_to_redis()
                    return True
                finally:
                    # 락 해제
                    cache.delete(ALS_TRAINING_LOCK_KEY)
            else:
                # 락 획득 실패 시 exponential backoff으로 재시도
                backoff = INITIAL_BACKOFF_SECONDS * (2**attempt)
                logger.info(f"[CACHE] Lock busy. Retry {attempt + 1}/{MAX_CACHE_LOAD_RETRIES} after {backoff:.1f}s")
                time.sleep(backoff)

        logger.error("[CACHE] Failed to load model after retries.")
        return False

    def _get_lectures_metadata_bulk(self, lecture_ids: List[int]) -> LectureMetadataMap:
        """
        강의 메타데이터 일괄 조회 (Redis pipeline 최적화)

        Args:
            lecture_ids: 조회할 강의 ID 리스트

        Returns:
            {강의_ID: (평점, 카테고리_ID_집합)} 매핑

        처리 로직:
        1. Redis pipeline으로 캐시 일괄 조회
        2. 캐시 미스 강의는 DB에서 조회
        3. DB 조회 결과를 캐시에 저장

        Note:
            - Redis pipeline으로 네트워크 왕복 최소화
            - 캐시 미스 시에만 DB 접근
        """
        metadata_map: LectureMetadataMap = {}
        miss_lecture_ids: List[int] = []

        # Redis pipeline으로 일괄 조회
        if self._is_redis_ready() and self.redis_conn:
            try:
                pipe = self.redis_conn.pipeline()
                for lec_id in lecture_ids:
                    cache_key = LECTURE_METADATA_CACHE_KEY.format(lec_id)
                    pipe.get(cache_key)

                cached_results = pipe.execute()

                # 캐시 히트/미스 분류
                for lec_id, cached_raw in zip(lecture_ids, cached_results):
                    if cached_raw:
                        metadata = self._metadata_get_safe(LECTURE_METADATA_CACHE_KEY.format(lec_id))
                        if metadata:
                            metadata_map[lec_id] = metadata
                        else:
                            miss_lecture_ids.append(lec_id)
                    else:
                        miss_lecture_ids.append(lec_id)
            except Exception as e:
                logger.warning(f"[CACHE] Redis pipeline failed: {e}. Falling back to individual queries.")
                miss_lecture_ids = lecture_ids
        else:
            miss_lecture_ids = lecture_ids

        # 캐시 미스 강의는 DB에서 조회
        if miss_lecture_ids:
            # 평점 조회
            ratings = CrawledLecture.objects.filter(id__in=miss_lecture_ids).values("id", "average_rating")
            ratings_map: Dict[int, float] = {
                r["id"]: float(r["average_rating"]) if r["average_rating"] is not None else 0.0 for r in ratings
            }

            # 카테고리 조회
            categories = LectureCategory.objects.filter(lecture_id__in=miss_lecture_ids).values(
                "lecture_id", "category_id"
            )
            categories_map: DefaultDict[int, Set[int]] = defaultdict(set)
            for cat in categories:
                lec_id = cat["lecture_id"]
                cat_id = cat["category_id"]
                categories_map[lec_id].add(cat_id)

            # 메타데이터 구성 및 캐시 저장
            for lec_id in miss_lecture_ids:
                avg_rating = ratings_map.get(lec_id, 0.0)
                category_ids = categories_map.get(lec_id, set())
                metadata_map[lec_id] = (avg_rating, category_ids)

                cache_key = LECTURE_METADATA_CACHE_KEY.format(lec_id)
                self._metadata_set_safe(cache_key, avg_rating, category_ids)

        return metadata_map

    def _get_user_prefer_categories(self, user_id: int) -> Set[int]:
        """
        사용자 선호 카테고리 조회 (캐싱 적용)

        Args:
            user_id: 사용자 ID

        Returns:
            사용자 선호 카테고리 ID 집합

        Note:
            - 캐시 TTL: 1시간
            - N+1 쿼리 방지를 위한 캐싱 전략
        """
        cache_key = f"user_prefer_cats_{user_id}"
        cached = cache.get(cache_key)

        if cached is not None:
            return cast(Set[int], cached)

        categories = UserPreferCategory.objects.category_ids_for_user(user_id)
        cache.set(cache_key, categories, 3600)  # 1시간 TTL
        return categories

    def _get_post_processed_ranking(self, user_id: int, recommended_idx_scores: List[Tuple[int, float]]) -> List[int]:
        """
        ALS 추천 결과에 평점/카테고리 보너스 적용 후 재정렬

        Args:
            user_id: 사용자 ID
            recommended_idx_scores: [(강의_인덱스, ALS_점수)] 리스트

        Returns:
            최종 점수 기준 정렬된 강의 ID 리스트

        처리 로직:
        1. ALS 점수에 power decay 적용 (극단값 완화)
        2. ALS 점수 정규화 (0-1 범위)
        3. 평점 보너스 추가 (정규화된 평점 × 가중치)
        4. 카테고리 매칭 보너스 추가 (매칭 수 × 가중치)
        5. 최종 점수로 재정렬

        Note:
            - 평점은 5점 만점 기준으로 정규화
            - 카테고리 매칭은 사용자 선호 카테고리와 강의 카테고리 교집합
            - DEBUG 모드에서 각 강의별 점수 분해 로그 출력
        """
        if not recommended_idx_scores:
            return []

        # 강의 인덱스 → 강의 ID 변환
        lecture_indices, als_scores = zip(*recommended_idx_scores)
        lecture_ids = [cast(Dict[int, int], self._lecture_idx_to_id)[idx] for idx in lecture_indices]

        # 강의 메타데이터 일괄 조회
        metadata_map: LectureMetadataMap = self._get_lectures_metadata_bulk(lecture_ids)

        # 사용자 선호 카테고리 조회
        user_prefer_cats: Set[int] = self._get_user_prefer_categories(user_id)

        # ALS 점수 배열 변환 및 power decay 적용
        als_scores_array = np.array(als_scores, dtype=np.float32)
        processed_als_scores = np.power(als_scores_array, ALS_SCORE_POWER_DECAY)

        # ALS 점수 정규화 (0-1 범위)
        if NORMALIZE_ALS_SCORE and processed_als_scores.size > 0:
            min_s = processed_als_scores.min()
            max_s = processed_als_scores.max()
            if max_s > min_s:
                normalized_als_scores = (processed_als_scores - min_s) / (max_s - min_s)
            else:
                # 모든 점수가 동일한 경우
                logger.debug(
                    "[RECSCORE] All ALS scores identical (%s after decay). Setting normalized scores to 0.",
                    f"{min_s:.3f}",
                )
                normalized_als_scores = processed_als_scores * 0
        else:
            normalized_als_scores = np.array([])

        # 최종 점수 계산 (ALS + 평점 보너스 + 카테고리 보너스)
        final_scores: List[Tuple[int, float]] = []
        for i, lec_id in enumerate(lecture_ids):
            # 강의 메타데이터 조회
            avg_rating, lec_cats = metadata_map.get(lec_id, (0.0, set()))
            # 정규화된 ALS 점수
            final_als_score = (
                normalized_als_scores[i] if normalized_als_scores.size > 0 and i < normalized_als_scores.size else 0.0
            )
            # 평점 보너스 (5점 만점 기준 정규화)
            normalized_rating = avg_rating / 5.0
            rating_bonus = normalized_rating * REVIEW_RATING_MULTIPLIER
            # 카테고리 매칭 보너스 (사용자 선호 카테고리 ∩ 강의 카테고리)
            matched_cats = user_prefer_cats.intersection(lec_cats)
            category_bonus = len(matched_cats) * CATEGORY_MATCH_BONUS
            # 최종 점수 = ALS 점수 + 평점 보너스 + 카테고리 보너스
            final_score = final_als_score + rating_bonus + category_bonus
            final_scores.append((lec_id, final_score))

            # 점수 분해 로그
            logger.debug(
                "[RECSCORE][U:%s] L:%s: ALS_Final(%.3f) + R(%.3f) + C(%.3f) -> Final(%.3f)",
                user_id,
                lec_id,
                final_als_score,
                rating_bonus,
                category_bonus,
                final_score,
            )

        # 최종 점수 기준 내림차순 정렬
        final_scores.sort(key=lambda x: x[1], reverse=True)
        return [lec_id for lec_id, _ in final_scores]

    def _get_popular_lectures(self, user_id: int, top_n: int) -> LectureQuerySet:
        """
        인기 강의 조회 (북마크 제외, 캐시 활용)

        Args:
            user_id: 사용자 ID
            top_n: 반환할 강의 수

        Returns:
            인기 강의 QuerySet

        처리 로직:
        1. 캐시에서 인기 강의 ID 리스트 조회
        2. 캐시 미스 시 DB에서 조회 후 캐시 저장
        3. Manager 메서드로 북마크 제외 및 정렬
        """
        # 캐시에서 인기 강의 ID 조회
        cached_ids = cache.get(POPULAR_LECTURE_CACHE_KEY)

        if cached_ids:
            # 캐시 히트: Manager 메서드 활용
            popular_ids = cached_ids[: top_n * 2]
        else:
            try:
                # 캐시용 쿼리 실행
                unfiltered_all_ids = list(
                    CrawledLecture.objects.all()
                    .order_by(POPULAR_LECTURE_ORDER_BY)[: top_n * 2]
                    .values_list("id", flat=True)
                )

                if unfiltered_all_ids:
                    cache.set(
                        POPULAR_LECTURE_CACHE_KEY,
                        unfiltered_all_ids,
                        POPULAR_LECTURE_TTL,
                    )

                popular_ids = unfiltered_all_ids
            except Exception as e:
                logger.error(f"[FALLBACK] Error fetching popular lectures from DB: {e}")
                # 폴백: 최신 강의 ID 내림차순
                popular_ids = list(
                    CrawledLecture.objects.all().order_by("-id").values_list("id", flat=True)[: top_n * 2]
                )

        # 빈 결과 처리
        if not popular_ids:
            return CrawledLecture.objects.none()

        return (
            CrawledLecture.objects.filter(id__in=popular_ids)
            .exclude_bookmarked(user_id)
            .ordered_by_ids(popular_ids[:top_n])
            .with_categories()
        )

    def _get_category_fallback(self, user_id: int, top_n: int) -> LectureQuerySet:
        """
        선호 카테고리 기반 강의 조회 (북마크 제외)

        Args:
            user_id: 사용자 ID
            top_n: 반환할 강의 수

        Returns:
            카테고리 기반 추천 QuerySet

        처리 로직:
        1. 사용자 선호 카테고리 조회
        2. 선호 카테고리 없으면 인기 강의로 폴백
        3. Manager 메서드로 북마크 제외 및 정렬
        """
        # 사용자 선호 카테고리 조회
        user_prefer_cats = set(UserPreferCategory.objects.filter(user_id=user_id).values_list("category_id", flat=True))

        # 선호 카테고리 없으면 인기 강의로 폴백
        if not user_prefer_cats:
            logger.info(f"[COLD_START] User {user_id} has no preferred categories. Using Popular Fallback.")
            return self._get_popular_lectures(user_id, top_n)

        # 선호 카테고리 강의 조회
        filtered_qs = (
            CrawledLecture.objects.filter(lecture_categories__category_id__in=user_prefer_cats)
            .distinct()
            .order_by(POPULAR_LECTURE_ORDER_BY)
        )

        try:
            # top_n * 2 조회 (충분한 후보 확보)
            ids = list(filtered_qs.values_list("id", flat=True)[: top_n * 2])

            # 결과 없으면 인기 강의로 폴백
            if not ids:
                return self._get_popular_lectures(user_id, top_n)

            # 랜덤 샘플링 (다양성 확보)
            random_ids = sample(ids, min(top_n, len(ids)))

            return (
                CrawledLecture.objects.filter(id__in=random_ids)
                .exclude_bookmarked(user_id)
                .ordered_by_ids(random_ids)
                .with_categories()
            )
        except Exception as e:
            logger.error(f"[FALLBACK] Error fetching category fallback: {e}")
            return filtered_qs.exclude_bookmarked(user_id).with_categories()[:top_n]

    def recommend_lectures(self, user_id: int, top_n: int = 10) -> LectureQuerySet:
        """
        사용자 맞춤 강의 추천 (ALS → Category Fallback → Popular Fallback)

        Args:
            user_id: 사용자 ID
            top_n: 반환할 강의 수 (기본값: 10)

        Returns:
            추천 강의 QuerySet

        Raises:
            ValueError: 입력 검증 실패 시

        처리 흐름:
        1, 2. 입력 검증 (user_id, top_n)
        3. 모델 로드 확인 (실패 시 카테고리 폴백)
        4. 사용자 인덱스 확인 (없으면 카테고리 폴백)
        5. ALS 추천 실행 (top_n * 5 조회)
        6. 후처리 점수 계산 및 재정렬
        7. 결과 부족 시 카테고리 폴백으로 보충
        8. 최종 QuerySet 반환

        Note:
            - ALS 실패 시 자동으로 카테고리 폴백
            - 추천 결과 로그 출력 (디버깅용)
            - 입력 검증 강화로 보안 및 안정성 확보
        """

        # 입력 검증
        # 1. user_id 타입 및 범위 검증
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"Invalid user_id: {user_id}. Must be a positive integer.")

        # 2. top_n 타입 및 범위 검증
        if not isinstance(top_n, int):
            raise ValueError(f"Invalid top_n type: {type(top_n)}. Must be an integer.")

        if top_n <= 0:
            logger.warning(f"[REC] Invalid top_n value: {top_n}. Using default value 10.")
            top_n = 10
        elif top_n > 100:
            logger.warning(f"[REC] top_n too large: {top_n}. Capping at 100.")
            top_n = 100

        # 3. 모델 로드 확인
        if not self._ensure_model_loaded() or self._model is None or self._user_items_matrix is None:
            logger.warning(f"[REC] Model not available for user {user_id}. Using Category Fallback.")
            return self._get_category_fallback(user_id, top_n)

        # 4. 사용자 인덱스 확인
        user_index = cast(Dict[int, int], self._user_to_idx).get(user_id)
        if user_index is None:
            logger.warning(f"[REC] User {user_id} not in model mapping. Using Category Fallback.")
            return self._get_category_fallback(user_id, top_n)

        rec_ids = []
        try:
            # 5. ALS 추천 실행 (implicit 라이브러리)
            result = self._model.recommend(
                userid=user_index,
                user_items=self._user_items_matrix[user_index],  # 단일 사용자 행만 전달
                N=top_n * 5,  # 후처리 여유분 확보
                filter_already_liked_items=True,  # 이미 상호작용한 강의 제외
                recalculate_user=True,  # 사용자 벡터 재계산
            )

            # 반환 형식 확인 및 처리 (버전 호환성)
            recommended_idx_scores = []
            if isinstance(result, tuple) and len(result) == 2:
                # 신버전: (indices, scores) 형태
                indices, scores = result
                # NumPy 배열을 리스트로 변환
                if hasattr(indices, "tolist"):
                    indices = indices.tolist()
                if hasattr(scores, "tolist"):
                    scores = scores.tolist()
                recommended_idx_scores = list(zip(indices, scores))
            elif isinstance(result, list):
                # 구버전: [(idx, score), ...] 형태
                recommended_idx_scores = result
            else:
                # 예상치 못한 형식
                logger.error(f"[REC] Unexpected result format from recommend(): {type(result)}")
                return self._get_category_fallback(user_id, top_n)

            # 추천 결과 없으면 폴백
            if not recommended_idx_scores:
                logger.warning(f"[REC] No recommendations returned for user {user_id}")
                return self._get_category_fallback(user_id, top_n)

            # 6. 후처리 점수 계산 및 재정렬
            final_ranked_ids = self._get_post_processed_ranking(user_id, recommended_idx_scores)
            rec_ids = final_ranked_ids[:top_n]
        except Exception as e:
            # ALS 추천 실패 시 카테고리 폴백
            logger.error(f"[REC] ALS recommendation failed for user {user_id}: {e}", exc_info=True)
            return self._get_category_fallback(user_id, top_n)

        # 7. 결과 부족 시 카테고리 폴백으로 보충
        if len(rec_ids) < top_n:
            needed_count = top_n - len(rec_ids)
            logger.info(
                f"[REC] ALS only returned {len(rec_ids)} results. Filling {needed_count} with Category Fallback."
            )

            # 카테고리 폴백으로 부족한 개수만큼 조회
            fallback_qs = self._get_category_fallback(user_id, needed_count)
            fallback_ids = list(fallback_qs.values_list("id", flat=True))

            # 중복 제거하며 추가
            for lec_id in fallback_ids:
                if lec_id not in rec_ids:
                    rec_ids.append(lec_id)
                    if len(rec_ids) == top_n:
                        break

        # 빈 결과 처리
        if not rec_ids:
            return CrawledLecture.objects.none()

        # 8. 최종 QuerySet 반환 (Manager 메서드가 북마크 제외 처리)
        qs = CrawledLecture.objects.ordered_by_ids(rec_ids).exclude_bookmarked(user_id).with_categories()

        # 추천 결과 로그 출력 (디버깅용)
        logger.info(f"[RECOMMENDATION_RESULT][{user_id}] IDs: {rec_ids}")
        return qs
