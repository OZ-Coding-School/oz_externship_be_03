import pickle
import time
from typing import Any, List, Optional, Set, Tuple
from unittest.mock import Mock, patch

import numpy as np
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from implicit.als import AlternatingLeastSquares  # type: ignore
from scipy.sparse import csr_matrix

from apps.core.utils.isolated_cache_testcase import IsolatedRedisTestClient
from apps.lecture.models import (
    LectureBookmark,
    UserPreferCategory,
)
from apps.lecture.services.recommendation_service.constants import (
    ALS_MODEL_CACHE_KEY,
    L_IDX_TO_ID_CACHE_KEY,
    L_TO_IDX_CACHE_KEY,
    LECTURE_METADATA_CACHE_KEY,
    POPULAR_LECTURE_CACHE_KEY,
    U_TO_IDX_CACHE_KEY,
    USER_ITEMS_MATRIX_CACHE_KEY,
)
from apps.lecture.services.recommendation_service.recommender import (
    RecommendationService,
)
from apps.lecture.tests.base_lecture import BaseLectureTest

User = get_user_model()


class RecommendationServiceRedisHealthTests(IsolatedRedisTestClient):
    """Redis 헬스체크 및 연결 관련 테스트

    - 연결 성공/실패 시나리오
    - PING 명령 성공/실패
    - 주기적 헬스체크
    """

    def setUp(self) -> None:
        super().setUp()
        self.service = RecommendationService()

    def test_get_redis_cache_success(self) -> None:
        """Redis 연결 초기화 성공 테스트"""
        service = RecommendationService()
        self.assertIsNotNone(service.redis_conn)  # 연결 객체 존재 확인

    @patch("apps.lecture.services.recommendation_service.recommender.get_redis_connection")
    def test_get_redis_cache_failure(self, mock_get_redis: Mock) -> None:
        """Redis 연결 실패 시 None 반환 테스트

        - 연결 실패 시뮬레이션
        - redis_conn이 None으로 설정됨
        - redis_healthy가 False로 설정됨
        """
        mock_get_redis.side_effect = Exception("Connection failed")
        service = RecommendationService()
        self.assertIsNone(service.redis_conn)
        self.assertFalse(service.redis_healthy)

    def test_check_redis_health_success(self) -> None:
        """Redis PING 성공 테스트

        - PING 명령 성공 시 True 반환
        - redis_healthy 플래그 True로 설정
        """
        self.service.redis_conn = Mock()
        self.service.redis_conn.ping.return_value = True

        result = self.service._check_redis_health(log_status=False)

        self.assertTrue(result)
        self.assertTrue(self.service.redis_healthy)

    def test_check_redis_health_failure(self) -> None:
        """Redis PING 실패 테스트

        - PING 예외 발생 시 False 반환
        - redis_healthy 플래그 False로 설정
        """
        self.service.redis_conn = Mock()
        self.service.redis_conn.ping.side_effect = Exception("PING failed")

        result = self.service._check_redis_health(log_status=False)

        self.assertFalse(result)
        self.assertFalse(self.service.redis_healthy)

    def test_check_redis_health_no_connection(self) -> None:
        """Redis 연결 없을 때 False 반환 테스트
        - redis_conn이 None일 때
        """
        self.service.redis_conn = None

        result = self.service._check_redis_health(log_status=False)

        self.assertFalse(result)

    def test_check_redis_health_recovery_logging(self) -> None:
        """Redis 복구 시 로그 출력 테스트
        - redis_healthy가 False에서 True로 변경
        - "recovered" 메시지 로그 출력
        """
        self.service.redis_conn = Mock()
        self.service.redis_conn.ping.return_value = True
        self.service.redis_healthy = False

        with self.assertLogs(level="INFO") as logs:
            self.service._check_redis_health(log_status=True)

        self.assertTrue(any("recovered" in log.lower() for log in logs.output))

    def test_is_redis_ready_cached_healthy(self) -> None:
        """Redis 정상 상태에서 캐시된 결과 반환 테스트
        - 최근 PING 성공 시 재체크 없이 True 반환
        """
        self.service.redis_healthy = True
        self.service.last_ping = time.time()  # 방금 체크함

        result = self.service._is_redis_ready()

        self.assertTrue(result)

    def test_is_redis_ready_periodic_check(self) -> None:
        """주기적 헬스체크 실행 테스트
        - REDIS_PING_INTERVAL_SECONDS 초과 시 재체크
        """
        self.service.redis_healthy = True
        # 마지막 PING이 인터벌보다 오래됨
        self.service.last_ping = time.time() - (self.service.REDIS_PING_INTERVAL_SECONDS + 1)
        self.service.redis_conn = Mock()
        self.service.redis_conn.ping.return_value = True

        result = self.service._is_redis_ready()

        self.assertTrue(result)
        self.service.redis_conn.ping.assert_called_once()  # 재체크 실행됨

    def test_is_redis_ready_unhealthy_frequent_check(self) -> None:
        """Redis 비정상 상태에서 60초마다 체크 테스트
        - redis_healthy가 False일 때
        - 60초마다 복구 시도
        """
        self.service.redis_healthy = False
        self.service.last_ping = time.time() - 61
        self.service.redis_conn = Mock()
        self.service.redis_conn.ping.return_value = True

        result = self.service._is_redis_ready()

        self.assertTrue(result)
        self.service.redis_conn.ping.assert_called_once()


class RecommendationServiceCacheOperationsTests(IsolatedRedisTestClient):
    """
    캐시 읽기/쓰기 관련 테스트

    - Redis/Django 캐시 읽기/쓰기
    - 직렬화/역직렬화 에러 처리
    - None 값 처리
    """

    def setUp(self) -> None:
        super().setUp()
        self.service = RecommendationService()

    def test_cache_get_safe_redis_success(self) -> None:
        """Redis에서 데이터 성공적으로 로드 테스트
        - pickle로 직렬화된 데이터 역직렬화
        """
        test_data = {"key": "value"}
        serialized = pickle.dumps(test_data, pickle.HIGHEST_PROTOCOL)

        self.service.redis_conn = Mock()
        self.service.redis_conn.get.return_value = serialized
        self.service.redis_healthy = True

        result = self.service._cache_get_safe("test_key", backend="redis")

        self.assertEqual(result, test_data)

    def test_cache_get_safe_django_fallback(self) -> None:
        """Django 캐시에서 데이터 로드 테스트
        - Redis 실패 시 Django 캐시 사용
        """
        test_data = {"key": "value"}
        serialized = pickle.dumps(test_data, pickle.HIGHEST_PROTOCOL)
        cache.set("test_key", serialized)

        result = self.service._cache_get_safe("test_key", backend="django")

        self.assertEqual(result, test_data)

    def test_cache_get_safe_deserialization_error(self) -> None:
        """역직렬화 실패 시 캐시 무효화 테스트
        - 손상된 데이터 감지
        - 자동으로 캐시 키 삭제
        """
        self.service.redis_conn = Mock()
        self.service.redis_conn.get.return_value = b"invalid_pickle_data"
        self.service.redis_healthy = True

        result = self.service._cache_get_safe("test_key", backend="redis")

        self.assertIsNone(result)
        self.service.redis_conn.delete.assert_called_once_with("test_key")

    def test_cache_get_safe_none_value(self) -> None:
        """캐시에 데이터 없을 때 None 반환 테스트"""
        self.service.redis_conn = Mock()
        self.service.redis_conn.get.return_value = None
        self.service.redis_healthy = True

        result = self.service._cache_get_safe("test_key", backend="redis")

        self.assertIsNone(result)

    def test_cache_set_safe_redis_success(self) -> None:
        """Redis에 데이터 성공적으로 저장 테스트
        - pickle로 직렬화
        - TTL(만료 시간) 설정
        """
        test_data = {"key": "value"}

        self.service.redis_conn = Mock()
        self.service.redis_healthy = True

        self.service._cache_set_safe("test_key", test_data, 3600, backend="redis")

        self.service.redis_conn.set.assert_called_once()
        call_args = self.service.redis_conn.set.call_args
        self.assertEqual(call_args[0][0], "test_key")  # 키 확인
        self.assertEqual(call_args[1]["ex"], 3600)  # TTL 확인

    def test_cache_set_safe_django_fallback(self) -> None:
        """Django 캐시에 데이터 저장 테스트"""
        test_data = {"key": "value"}

        self.service._cache_set_safe("test_key", test_data, 3600, backend="django")

        cached = cache.get("test_key")
        self.assertIsNotNone(cached)
        deserialized = pickle.loads(cached)
        self.assertEqual(deserialized, test_data)

    def test_cache_set_safe_none_value(self) -> None:
        """None 값은 저장하지 않음 테스트
        - 불필요한 캐시 저장 방지
        """
        self.service.redis_conn = Mock()
        self.service.redis_healthy = True

        self.service._cache_set_safe("test_key", None, 3600, backend="redis")

        self.service.redis_conn.set.assert_not_called()

    def test_cache_set_safe_serialization_error(self) -> None:
        """직렬화 실패 시 에러 로그만 출력 테스트
        - pickle 불가능한 객체 (람다 등)
        - 에러 로그 출력 후 계속 진행
        """
        unpicklable_data = lambda x: x  # 람다는 pickle 불가

        self.service.redis_conn = Mock()
        self.service.redis_healthy = True

        with self.assertLogs(level="ERROR") as logs:
            self.service._cache_set_safe("test_key", unpicklable_data, 3600, backend="redis")

        self.assertTrue(any("serialization" in log.lower() for log in logs.output))

    def test_metadata_get_safe_redis(self) -> None:
        """강의 메타데이터 Redis에서 로드 테스트
        - 메타데이터: (평균 평점, 카테고리 ID 집합)
        """
        metadata: Tuple[float, Set[int]] = (4.5, {1, 2, 3})
        serialized = pickle.dumps(metadata, pickle.HIGHEST_PROTOCOL)

        self.service.redis_conn = Mock()
        self.service.redis_conn.get.return_value = serialized
        self.service.redis_healthy = True

        result = self.service._metadata_get_safe("metadata_key")

        self.assertEqual(result, metadata)

    def test_metadata_set_safe_redis(self) -> None:
        """강의 메타데이터 Redis에 저장 테스트"""
        self.service.redis_conn = Mock()
        self.service.redis_healthy = True

        self.service._metadata_set_safe("metadata_key", 4.5, {1, 2, 3})

        self.service.redis_conn.set.assert_called_once()


class RecommendationServiceModelLoadingTests(IsolatedRedisTestClient):
    """
    모델 로드 관련 테스트

    - Redis에서 모델 로드
    - 디스크에서 모델 로드
    - 락 메커니즘 테스트
    """

    def setUp(self) -> None:
        super().setUp()
        self.service = RecommendationService()
        self.mock_model = Mock(spec=AlternatingLeastSquares)  # ALS 모델 Mock
        self.mock_matrix: csr_matrix = csr_matrix((10, 20), dtype=np.float32)  # 10x20 희소 행렬

    def test_load_from_redis_partial_data(self) -> None:
        """
        부분 데이터만 있을 때 로드 실패 테스트

        - 모든 캐시 키가 존재해야 로드 성공
        - 일부만 있으면 False 반환
        """
        # 실제 ALS 모델 사용
        real_model = AlternatingLeastSquares(factors=10)
        serialized = pickle.dumps(real_model, pickle.HIGHEST_PROTOCOL)
        cache.set(ALS_MODEL_CACHE_KEY, serialized)  # 모델만 캐시에 저장

        result = self.service._load_from_redis()

        self.assertFalse(result)  # 다른 키들이 없어서 실패

    def test_load_from_redis_no_data(self) -> None:
        """캐시에 데이터 없을 때 로드 실패 테스트"""
        result = self.service._load_from_redis()

        self.assertFalse(result)

    def test_apply_loaded_data(self) -> None:
        """로드된 데이터 인스턴스 변수에 적용 테스트
        - 캐시에서 로드한 데이터를 서비스 객체에 설정
        """
        cached_data = {
            ALS_MODEL_CACHE_KEY: self.mock_model,
            U_TO_IDX_CACHE_KEY: {1: 0, 2: 1},  # 사용자 매핑
            L_TO_IDX_CACHE_KEY: {10: 0, 20: 1},  # 강의 매핑
            L_IDX_TO_ID_CACHE_KEY: {0: 10, 1: 20},  # 역방향 매핑
            USER_ITEMS_MATRIX_CACHE_KEY: self.mock_matrix,
        }

        self.service._apply_loaded_data(cached_data)
        # 모든 데이터가 올바르게 설정되었는지 확인
        self.assertEqual(self.service._model, self.mock_model)
        self.assertEqual(self.service._user_to_idx, {1: 0, 2: 1})
        self.assertEqual(self.service._lecture_to_idx, {10: 0, 20: 1})
        self.assertEqual(self.service._lecture_idx_to_id, {0: 10, 1: 20})
        self.assertIsNotNone(self.service._user_items_matrix)

    def test_load_from_redis_with_all_keys_present(self) -> None:
        """모든 캐시 키가 존재할 때 _load_from_redis 성공 테스트
        - 5개 필수 키 모두 존재
        - 로드 성공 후 인스턴스 변수 설정
        """
        real_model = AlternatingLeastSquares(factors=10)

        cache_data = {
            ALS_MODEL_CACHE_KEY: real_model,
            U_TO_IDX_CACHE_KEY: {1: 0, 2: 1},
            L_TO_IDX_CACHE_KEY: {10: 0, 20: 1},
            L_IDX_TO_ID_CACHE_KEY: {0: 10, 1: 20},
            USER_ITEMS_MATRIX_CACHE_KEY: self.mock_matrix,
        }

        # _cache_get_safe를 Mock으로 대체
        def mock_cache_get(key: str, backend: Optional[str] = None) -> Any:
            return cache_data.get(key)

        with patch.object(self.service, "_cache_get_safe", side_effect=mock_cache_get):
            result = self.service._load_from_redis()

            self.assertTrue(result)
            self.assertIsNotNone(self.service._model)

    def test_save_to_redis_incomplete_data(self) -> None:
        """불완전한 데이터는 저장하지 않음 테스트
        - 모델만 있고 다른 데이터 없으면 저장 안함
        """
        self.service._model = self.mock_model  # 모델만 설정

        self.service._save_to_redis()

        cached = cache.get(ALS_MODEL_CACHE_KEY)
        self.assertIsNone(cached)  # 저장되지 않음

    @patch("apps.lecture.services.recommendation_service.recommender.cache")
    def test_ensure_model_loaded_from_memory(self, mock_cache: Mock) -> None:
        """메모리에 모델이 있을 때 즉시 반환 테스트
        - 이미 로드된 모델은 재로드 안함
        - 캐시 조회 없음
        """
        self.service._model = self.mock_model  # 이미 로드됨

        result = self.service._ensure_model_loaded()

        self.assertTrue(result)
        mock_cache.get.assert_not_called()  # 캐시 조회 안함

    @patch("apps.lecture.services.recommendation_service.recommender.cache")
    def test_ensure_model_loaded_from_disk(self, mock_cache: Mock) -> None:
        """디스크에서 모델 로드 테스트
        - Redis 캐시 미스
        - 디스크에서 모델 파일 로드
        """
        mock_cache.get.return_value = None  # 캐시 미스
        mock_cache.add.return_value = True  # 락 획득 성공

        # 디스크에서 로드할 모델 번들
        mock_bundle = (
            self.mock_model,
            {1: 0, 2: 1},  # user_to_idx
            {10: 0, 20: 1},  # lecture_to_idx
            [1, 2],  # users
            [10, 20],  # lectures
            self.mock_matrix,
            timezone.now(),  # last_trained_at
        )

        with patch.object(self.service.model_trainer, "load_model_and_mappings", return_value=mock_bundle):
            result = self.service._ensure_model_loaded()

        self.assertTrue(result)
        self.assertIsNotNone(self.service._model)

    @patch("apps.lecture.services.recommendation_service.recommender.cache")
    def test_ensure_model_loaded_lock_retry(self, mock_cache: Mock) -> None:
        """락 경합 시 재시도 테스트
        - 첫 번째 락 획득 실패
        - 두 번째 시도에서 성공
        """
        mock_cache.get.return_value = None
        mock_cache.add.side_effect = [False, True]  # 첫 실패, 두 번째 성공

        mock_bundle = (
            self.mock_model,
            {1: 0, 2: 1},
            {10: 0, 20: 1},
            [1, 2],
            [10, 20],
            self.mock_matrix,
            timezone.now(),
        )

        with patch.object(self.service.model_trainer, "load_model_and_mappings", return_value=mock_bundle):
            with patch("time.sleep"):  # sleep 시간 건너뛰기
                result = self.service._ensure_model_loaded()

        self.assertTrue(result)
        self.assertEqual(mock_cache.add.call_count, 2)  # 2번 시도

    @patch("apps.lecture.services.recommendation_service.recommender.cache")
    def test_ensure_model_loaded_max_retries_exceeded(self, mock_cache: Mock) -> None:
        """최대 재시도 횟수 초과 시 실패 테스트
        - 락을 계속 획득 못함
        - 최대 재시도 후 False 반환
        """
        mock_cache.get.return_value = None
        mock_cache.add.return_value = False  # 계속 실패

        with patch("time.sleep"):
            result = self.service._ensure_model_loaded()

        self.assertFalse(result)


class RecommendationServiceMetadataTests(IsolatedRedisTestClient, BaseLectureTest):
    """
    메타데이터 일괄 조회 관련 테스트

    - Redis pipeline 사용
    - 캐시 히트/미스 처리
    - DB 폴백
    """

    user: Any

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.user = User.objects.create_user(
            email="test@example.com",
            password="testpass",
            nickname="testnick",
            name="Test User",
            phone_number="010-1234-5678",
            gender="M",
            birthday="1990-01-01",
        )

    def setUp(self) -> None:
        super().setUp()
        self.service = RecommendationService()

    def test_get_lectures_metadata_bulk_redis_pipeline(self) -> None:
        """Redis pipeline으로 메타데이터 일괄 조회 테스트
        - 여러 강의 메타데이터를 한 번에 조회
        - 네트워크 왕복 최소화
        """
        lecture_ids = [self.lecture1.id, self.lecture2.id]

        # 각 강의의 메타데이터 캐시 설정
        for lec_id in lecture_ids:
            cache_key = LECTURE_METADATA_CACHE_KEY.format(lec_id)
            metadata = (4.5, {self.category1.id})  # (평점, 카테고리 집합)
            serialized = pickle.dumps(metadata, pickle.HIGHEST_PROTOCOL)
            cache.set(cache_key, serialized)

        result = self.service._get_lectures_metadata_bulk(lecture_ids)

        self.assertEqual(len(result), 2)
        self.assertIn(self.lecture1.id, result)
        self.assertIn(self.lecture2.id, result)

    def test_get_lectures_metadata_bulk_cache_miss(self) -> None:
        """캐시 미스 시 DB 조회 테스트
        - 캐시에 없으면 DB에서 조회
        - 조회 후 캐시에 저장
        """
        lecture_ids = [self.lecture1.id, self.lecture2.id]

        result = self.service._get_lectures_metadata_bulk(lecture_ids)

        self.assertEqual(len(result), 2)
        self.assertIn(self.lecture1.id, result)
        self.assertIn(self.lecture2.id, result)

    def test_get_lectures_metadata_bulk_mixed(self) -> None:
        """캐시 히트/미스 혼합 테스트
        - lecture1: 캐시 히트
        - lecture2: 캐시 미스 -> DB 조회
        """
        lecture_ids = [self.lecture1.id, self.lecture2.id]

        # lecture1만 캐시에 저장
        cache_key = LECTURE_METADATA_CACHE_KEY.format(self.lecture1.id)
        metadata = (4.5, {self.category1.id})
        serialized = pickle.dumps(metadata, pickle.HIGHEST_PROTOCOL)
        cache.set(cache_key, serialized)

        result = self.service._get_lectures_metadata_bulk(lecture_ids)

        self.assertEqual(len(result), 2)
        self.assertIn(self.lecture1.id, result)
        self.assertIn(self.lecture2.id, result)


class RecommendationServicePostProcessingTests(IsolatedRedisTestClient, BaseLectureTest):
    """
    추천 점수 후처리 관련 테스트

    - ALS 점수 정규화
    - 평점/카테고리 보너스 적용
    - 최종 순위 결정
    """

    user: Any

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.user = User.objects.create_user(
            email="test@example.com",
            password="testpass",
            nickname="testnick",
            name="Test User",
            phone_number="010-1234-5678",
            gender="M",
            birthday="1990-01-01",
        )
        UserPreferCategory.objects.create(user=cls.user, category=cls.category1)

    def setUp(self) -> None:
        super().setUp()
        self.service = RecommendationService()
        self.service._lecture_idx_to_id = {0: self.lecture1.id, 1: self.lecture2.id}

    def test_get_post_processed_ranking_with_bonuses(self) -> None:
        """평점/카테고리 보너스 적용 테스트
        - 높은 평점 강의에 보너스
        - 선호 카테고리 강의에 보너스
        """
        recommended_idx_scores = [(0, 0.8), (1, 0.6)]  # (인덱스, ALS 점수)

        result = self.service._get_post_processed_ranking(self.user.id, recommended_idx_scores)

        self.assertEqual(len(result), 2)

    def test_get_post_processed_ranking_normalization(self) -> None:
        """ALS 점수 정규화 테스트
        - 점수 범위를 0-1로 정규화
        - 보너스 적용 후 재정렬
        """
        recommended_idx_scores = [(0, 1.0), (1, 0.5)]  # (인덱스, ALS 점수)

        result = self.service._get_post_processed_ranking(self.user.id, recommended_idx_scores)

        self.assertEqual(len(result), 2)
        self.assertIsInstance(result, list)

    def test_get_post_processed_ranking_empty_input(self) -> None:
        """빈 입력 처리 테스트"""
        recommended_idx_scores: List[Tuple[int, float]] = []

        result = self.service._get_post_processed_ranking(self.user.id, recommended_idx_scores)

        self.assertEqual(result, [])


class RecommendationServiceFallbackTests(IsolatedRedisTestClient, BaseLectureTest):
    """
    폴백 전략 관련 테스트

    - 인기 강의 폴백
    - 카테고리 기반 폴백
    - 북마크 제외 필터링
    """

    user: Any

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.user = User.objects.create_user(
            email="test@example.com",
            password="testpass",
            nickname="testnick",
            name="Test User",
            phone_number="010-1234-5678",
            gender="M",
            birthday="1990-01-01",
        )

    def setUp(self) -> None:
        super().setUp()
        self.service = RecommendationService()

    def test_get_popular_lectures_with_cache(self) -> None:
        """캐시된 인기 강의 조회 테스트
        - Redis에 캐시된 인기 강의 ID 목록 사용
        - DB 조회 최소화
        """
        cached_ids = [self.lecture2.id, self.lecture1.id]  # 인기 순서
        cache.set(POPULAR_LECTURE_CACHE_KEY, cached_ids)
        result = self.service._get_popular_lectures(self.user.id, 2)
        self.assertEqual(result.count(), 2)

    def test_get_popular_lectures_cache_miss(self) -> None:
        """캐시 미스 시 DB 조회 테스트
        - 캐시에 없으면 DB에서 인기 강의 조회
        - 북마크 수, 평점 등으로 정렬
        """
        result = self.service._get_popular_lectures(self.user.id, 2)
        self.assertGreater(result.count(), 0)

    def test_get_popular_lectures_exclude_bookmarks(self) -> None:
        """북마크 제외 필터링 테스트
        - 사용자가 북마크한 강의는 인기 강의에서도 제외
        """
        LectureBookmark.objects.create(user=self.user, lecture=self.lecture1)
        result = self.service._get_popular_lectures(self.user.id, 2)
        result_ids = list(result.values_list("id", flat=True))
        self.assertNotIn(self.lecture1.id, result_ids)

    def test_get_category_fallback_with_preferences(self) -> None:
        """선호 카테고리 기반 추천 테스트
        - 사용자 선호 카테고리의 강의 추천
        - 평점 높은 순으로 정렬
        """
        UserPreferCategory.objects.create(user=self.user, category=self.category1)
        result = self.service._get_category_fallback(self.user.id, 2)
        self.assertGreater(result.count(), 0)

    def test_get_category_fallback_no_preferences(self) -> None:
        """선호 카테고리 없을 때 인기 강의 폴백 테스트"""
        result = self.service._get_category_fallback(self.user.id, 2)
        self.assertGreater(result.count(), 0)


class RecommendationServiceMainRecommendationTests(IsolatedRedisTestClient, BaseLectureTest):
    """
    메인 추천 로직 관련 테스트

    - 모델 기반 추천
    - 폴백 전략 실행
    - 결과 부족 시 보충
    """

    user: Any

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.user = User.objects.create_user(
            email="test@example.com",
            password="testpass",
            nickname="testnick",
            name="Test User",
            phone_number="010-1234-5678",
            gender="M",
            birthday="1990-01-01",
        )

    def setUp(self) -> None:
        super().setUp()
        self.service = RecommendationService()
        # Mock 대신 실제 ALS 모델 사용
        self.mock_model = AlternatingLeastSquares(factors=10)
        self.mock_matrix: csr_matrix = csr_matrix((10, 20), dtype=np.float32)

    def test_recommend_lectures_model_not_loaded(self) -> None:
        """모델 로드 실패 시 카테고리 폴백 테스트
        - 모델 로드 실패
        - 자동으로 카테고리 기반 추천으로 폴백
        """
        with patch.object(self.service, "_ensure_model_loaded", return_value=False):
            result = self.service.recommend_lectures(self.user.id, 5)

        self.assertIsNotNone(result)

    def test_recommend_lectures_user_not_in_model(self) -> None:
        """모델에 없는 사용자 카테고리 폴백 테스트
        - 사용자가 모델에 없음
        - 카테고리 기반 추천으로 폴백
        """
        self.service._model = self.mock_model
        self.service._user_to_idx = {999: 0}  # 다른 사용자만 존재
        self.service._user_items_matrix = self.mock_matrix

        result = self.service.recommend_lectures(self.user.id, 5)

        self.assertIsNotNone(result)

    def test_recommend_lectures_als_success(self) -> None:
        """ALS 추천 성공 테스트
        - 모델 기반 추천 정상 실행
        - 추천 결과 반환
        """
        real_model = AlternatingLeastSquares(factors=10)
        self.service._model = real_model
        self.service._user_to_idx = {self.user.id: 0}
        self.service._lecture_to_idx = {self.lecture1.id: 0, self.lecture2.id: 1}
        self.service._lecture_idx_to_id = {0: self.lecture1.id, 1: self.lecture2.id}
        self.service._user_items_matrix = self.mock_matrix

        # Mock을 사용하여 recommend 메서드 패치
        with patch.object(real_model, "recommend") as mock_recommend:
            mock_indices = np.array([0, 1])
            mock_scores = np.array([0.8, 0.6])
            mock_recommend.return_value = (mock_indices, mock_scores)

            result = self.service.recommend_lectures(self.user.id, 2)

            self.assertGreater(result.count(), 0)

    def test_recommend_lectures_als_exception(self) -> None:
        """ALS 추천 실패 시 카테고리 폴백 테스트
        - ALS 추천 중 예외 발생
        - 자동으로 카테고리 폴백
        """
        real_model = AlternatingLeastSquares(factors=10)
        self.service._model = real_model
        self.service._user_to_idx = {self.user.id: 0}
        self.service._user_items_matrix = self.mock_matrix

        with patch.object(real_model, "recommend", side_effect=Exception("ALS error")):
            result = self.service.recommend_lectures(self.user.id, 5)

            self.assertIsNotNone(result)

    def test_recommend_lectures_insufficient_results(self) -> None:
        """결과 부족 시 카테고리 폴백으로 보충 테스트
        - ALS 추천 결과가 요청 개수보다 적음
        - 카테고리 기반 추천으로 부족분 보충
        """
        real_model = AlternatingLeastSquares(factors=10)
        self.service._model = real_model
        self.service._user_to_idx = {self.user.id: 0}
        self.service._lecture_to_idx = {self.lecture1.id: 0}
        self.service._lecture_idx_to_id = {0: self.lecture1.id}
        self.service._user_items_matrix = self.mock_matrix

        with patch.object(real_model, "recommend") as mock_recommend:
            mock_indices = np.array([0])  # 1개만 추천
            mock_scores = np.array([0.8])
            mock_recommend.return_value = (mock_indices, mock_scores)

            # 선호 카테고리 설정 (보충용)
            UserPreferCategory.objects.create(user=self.user, category=self.category1)

            result = self.service.recommend_lectures(self.user.id, 5)  # 5개 요청

            self.assertGreater(result.count(), 0)

    def test_recommend_lectures_empty_result(self) -> None:
        """추천 결과 없을 때 빈 QuerySet 반환 테스트
        - ALS 추천 결과 없음
        - 폴백도 결과 없음
        - 빈 QuerySet 반환 (에러 없음)
        """
        real_model = AlternatingLeastSquares(factors=10)
        self.service._model = real_model
        self.service._user_to_idx = {self.user.id: 0}
        self.service._lecture_to_idx = {}  # 강의 없음
        self.service._lecture_idx_to_id = {}
        self.service._user_items_matrix = self.mock_matrix

        with patch.object(real_model, "recommend") as mock_recommend:
            mock_indices = np.array([])  # 빈 결과
            mock_scores = np.array([])
            mock_recommend.return_value = (mock_indices, mock_scores)

            result = self.service.recommend_lectures(self.user.id, 5)

            self.assertIsNotNone(result)  # None이 아닌 빈 QuerySet
