import logging
import os
import time
import unittest
from contextlib import contextmanager
from typing import Any, Callable, Generator, List, Optional, Tuple
from unittest import mock

import numpy as np
from django.core.cache import cache
from implicit.als import AlternatingLeastSquares  # type: ignore
from scipy.sparse import csr_matrix

from apps.core.utils.isolated_cache_testcase import IsolatedRedisTestClient
from apps.lecture.models import (
    CrawledLecture,
    LectureBookmark,
    UserPreferCategory,
)
from apps.lecture.services.recommendation_service.constants import (
    ALS_MODEL_CACHE_KEY,
    L_TO_IDX_CACHE_KEY,
    U_TO_IDX_CACHE_KEY,
)
from apps.lecture.services.recommendation_service.recommender import (
    RecommendationService,
)
from apps.lecture.tests.base_lecture import BaseLectureTest
from apps.users.models import User


class RecommendationServiceTestBase(IsolatedRedisTestClient, BaseLectureTest):
    """RecommendationService 테스트 Base 클래스"""

    service: RecommendationService
    user1: User
    user2: User

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()

        cls.user1 = User.objects.create(
            email="test1@example.com",
            name="테스트 사용자 1",
            nickname="testuser1",
            phone_number="010-1234-5678",
            gender="MALE",
            birthday="1990-01-01",
        )
        cls.user2 = User.objects.create(
            email="test2@example.com",
            name="테스트 사용자 2",
            nickname="testuser2",
            phone_number="010-1234-5679",
            gender="FEMALE",
            birthday="1991-01-01",
        )

    def setUp(self) -> None:
        """각 테스트마다 새로운 RecommendationService 인스턴스 생성"""
        # 프로세스별 고유 prefix 생성 (병렬 테스트 격리)
        worker_id = os.getpid()
        self.cache_prefix = f"test_{worker_id}_"

        self.service = RecommendationService()

    def tearDown(self) -> None:
        """각 테스트 후 프로세스별 캐시 키만 정리"""
        super().tearDown()

        # 프로세스별 캐시 키만 삭제
        if hasattr(self, "cache_prefix"):
            # 테스트에서 사용한 키들을 명시적으로 삭제
            test_keys = [
                f"{self.cache_prefix}test_key",
                f"{self.cache_prefix}test_ttl_key",
                f"{self.cache_prefix}{ALS_MODEL_CACHE_KEY}",
                f"{self.cache_prefix}{U_TO_IDX_CACHE_KEY}",
                f"{self.cache_prefix}{L_TO_IDX_CACHE_KEY}",
            ]
            cache.delete_many(test_keys)

        if hasattr(self.service, "redis_conn") and self.service.redis_conn:
            try:
                self.service.redis_conn.ping()
            except Exception:
                self.service.redis_conn = self.service._get_redis_cache()
                self.service.redis_healthy = self.service._check_redis_health(log_status=False)

    @staticmethod
    def _create_lecture(title: str, **kwargs: Any) -> CrawledLecture:
        """테스트용 강의 생성 헬퍼"""
        defaults = {
            "instructor": "테스트 강사",
            "average_rating": 4.5,
            "duration": 300,
            "difficulty": "NORMAL",
            "description": "테스트 설명",
            "platform": "INFLEARN",
            "url_link": f"https://test.com/{title}",
        }
        defaults.update(kwargs)
        return CrawledLecture.objects.create(title=title, **defaults)

    def _verify_cache_recovery(self) -> None:
        """캐시 연결 복구 검증"""
        recovery_key = f"{self.cache_prefix}recovery_test"
        cache.set(recovery_key, "value", timeout=10)
        self.assertEqual(cache.get(recovery_key), "value", "캐시 복구가 실패했습니다")
        cache.delete(recovery_key)

    @contextmanager
    def _mock_als_environment(
        self, user_id: int, model_behavior: Optional[Callable[[Any], None]] = None
    ) -> Generator[Any, None, None]:
        """ALS 환경을 Mock하는 컨텍스트 매니저"""
        mock_model = mock.Mock()
        if model_behavior:
            model_behavior(mock_model)

        with mock.patch.object(self.service, "_ensure_model_loaded", return_value=True):
            with mock.patch.object(self.service, "_model", mock_model):
                with mock.patch.object(self.service, "_user_items_matrix", csr_matrix((1, 1))):
                    with mock.patch.object(self.service, "_user_to_idx", {user_id: 0}):
                        yield mock_model


# ========================================
# 1. Redis 헬스체크 테스트
# ========================================
class RedisHealthCheckTestCase(RecommendationServiceTestBase):
    """Redis 헬스체크 테스트"""

    def test_get_redis_cache_success(self) -> None:
        """Redis 캐시 정상 연결 테스트"""
        redis_cache = self.service._get_redis_cache()
        self.assertIsNotNone(redis_cache, "Redis 캐시 객체가 None이 아니어야 합니다")

    def test_check_redis_health_success(self) -> None:
        """Redis 헬스체크 성공"""
        result = self.service._check_redis_health(log_status=False)
        self.assertTrue(result, "Redis 헬스체크가 성공해야 합니다")

    def test_check_redis_health_failure(self) -> None:
        """Redis 헬스체크 실패"""
        with mock.patch.object(self.service, "redis_conn", None):
            result = self.service._check_redis_health(log_status=False)
            self.assertFalse(result, "Redis 연결이 없으면 헬스체크가 실패해야 합니다")

    def test_is_redis_ready_success(self) -> None:
        """Redis 준비 상태 확인"""
        self.service.redis_healthy = True
        self.service.last_ping = time.time()
        result = self.service._is_redis_ready()
        self.assertTrue(result, "Redis가 준비 상태여야 합니다")


# ========================================
# 2. 캐시 읽기/쓰기 테스트
# ========================================
class CacheOperationsTestCase(RecommendationServiceTestBase):
    """캐시 읽기/쓰기 테스트"""

    def test_cache_get_safe_success(self) -> None:
        """캐시 안전 읽기 성공"""
        test_key = f"{self.cache_prefix}test_key"
        test_value = {"data": "test"}
        cache.set(test_key, test_value)
        result = self.service._cache_get_safe(test_key)
        self.assertEqual(result, test_value, "캐시에서 올바른 값을 읽어야 합니다")

    def test_cache_get_safe_miss(self) -> None:
        """캐시 미스"""
        nonexistent_key = f"{self.cache_prefix}nonexistent_key"
        result = self.service._cache_get_safe(nonexistent_key)
        self.assertIsNone(result, "존재하지 않는 키는 None을 반환해야 합니다")

    def test_cache_set_safe_success(self) -> None:
        """캐시 쓰기 성공"""
        test_key = f"{self.cache_prefix}test_key"
        test_value = {"data": "test"}
        self.service._cache_set_safe(test_key, test_value, timeout=60)
        cached_value = cache.get(test_key)
        self.assertEqual(cached_value, test_value, "캐시에 올바르게 저장되어야 합니다")

    def test_cache_get_safe_exception(self) -> None:
        """캐시 읽기 예외 처리"""
        test_key = f"{self.cache_prefix}test_key"
        with mock.patch.object(cache, "get", side_effect=Exception("Redis error")):
            result = self.service._cache_get_safe(test_key)
        self.assertIsNone(result, "예외 발생 시 None을 반환해야 합니다")

    def test_cache_set_safe_exception(self) -> None:
        """캐시 쓰기 예외 처리"""
        test_key = f"{self.cache_prefix}test_key"
        with mock.patch.object(cache, "set", side_effect=Exception("Redis error")):
            self.service._cache_set_safe(test_key, "test_value", timeout=60)

        self._verify_cache_recovery()


# ========================================
# 3. 모델 로딩 테스트
# ========================================
class ModelLoadingTestCase(RecommendationServiceTestBase):
    """모델 로딩 테스트"""

    def test_ensure_model_loaded_success(self) -> None:
        """모델 로드 성공"""
        with mock.patch.object(self.service, "_load_from_redis", return_value=True):
            with mock.patch.object(self.service, "_apply_loaded_data"):
                result = self.service._ensure_model_loaded()
                self.assertTrue(result, "모델 로드가 성공해야 합니다")

    def test_ensure_model_loaded_failure(self) -> None:
        """모델 로드 실패"""
        with mock.patch("time.sleep"):
            with mock.patch("apps.lecture.services.recommendation_service.constants.MAX_CACHE_LOAD_RETRIES", 2):
                with mock.patch.object(self.service, "_load_from_redis", return_value=False):
                    with mock.patch.object(cache, "add", return_value=False):
                        result = self.service._ensure_model_loaded()
                        self.assertFalse(result, "모델 로드가 실패해야 합니다")


# ========================================
# 4. 메타데이터 조회 테스트
# ========================================
class MetadataRetrievalTestCase(RecommendationServiceTestBase):
    """메타데이터 조회 테스트"""

    def test_get_user_prefer_categories_success(self) -> None:
        """사용자 선호 카테고리 조회"""
        UserPreferCategory.objects.create(user=self.user1, category=self.category1)

        result = self.service._get_user_prefer_categories(self.user1.id)

        self.assertEqual(len(result), 1, "1개의 카테고리가 반환되어야 합니다")
        self.assertIn(self.category1.id, result, "category1이 결과에 있어야 합니다")

    def test_get_lectures_metadata_bulk_empty(self) -> None:
        """빈 강의 ID 리스트"""
        result = self.service._get_lectures_metadata_bulk([])
        self.assertEqual(result, {}, "빈 리스트는 빈 딕셔너리를 반환해야 합니다")


# ========================================
# 5. 후처리 테스트
# ========================================
class PostProcessingTestCase(RecommendationServiceTestBase):
    """후처리 테스트"""

    def test_get_post_processed_ranking_basic(self) -> None:
        """기본 후처리"""
        user_id = self.user1.id
        als_scores: List[Tuple[int, float]] = [(0, 0.9), (1, 0.8)]

        with mock.patch.object(self.service, "_lecture_idx_to_id", {0: self.lecture1.id, 1: self.lecture2.id}):
            result = self.service._get_post_processed_ranking(user_id, als_scores)

            self.assertIsInstance(result, list, "결과는 리스트여야 합니다")
            self.assertEqual(len(result), 2, "2개의 결과를 반환해야 합니다")
            self.assertIn(self.lecture1.id, result, "강의1이 결과에 있어야 합니다")

    def test_get_post_processed_ranking_empty_scores(self) -> None:
        """빈 ALS 점수 리스트"""
        user_id = self.user1.id
        als_scores: List[Tuple[int, float]] = []

        with mock.patch.object(self.service, "_lecture_idx_to_id", {}):
            result = self.service._get_post_processed_ranking(user_id, als_scores)
            self.assertEqual(result, [], "빈 점수는 빈 리스트를 반환해야 합니다")


# ========================================
# 6. 폴백 전략 테스트
# ========================================
class FallbackStrategyTestCase(RecommendationServiceTestBase):
    """폴백 전략 테스트"""

    def test_get_popular_lectures_success(self) -> None:
        """인기 강의 폴백"""
        LectureBookmark.objects.create(user=self.user1, lecture=self.lecture1)
        LectureBookmark.objects.create(user=self.user2, lecture=self.lecture1)

        result = self.service._get_popular_lectures(self.user1.id, top_n=10)

        self.assertIsNotNone(result, "결과가 None이 아니어야 합니다")
        self.assertGreater(result.count(), 0, "최소 1개의 강의를 반환해야 합니다")
        result_ids = list(result.values_list("id", flat=True))
        self.assertNotIn(self.lecture1.id, result_ids, "북마크된 강의는 제외되어야 합니다")

        # 실제로 인기도 순으로 정렬되었는지 검증
        if result.count() > 1:
            ratings = list(result.values_list("average_rating", flat=True))
            self.assertEqual(ratings, sorted(ratings, reverse=True), "평점 순으로 정렬되어야 합니다")

    def test_get_category_fallback_success(self) -> None:
        """카테고리 폴백"""
        UserPreferCategory.objects.create(user=self.user1, category=self.category1)

        result = self.service._get_category_fallback(self.user1.id, top_n=10)

        self.assertIsNotNone(result, "결과가 None이 아니어야 합니다")
        self.assertGreater(result.count(), 0, "최소 1개의 강의를 반환해야 합니다")


# ========================================
# 7. 메인 추천 메서드 테스트
# ========================================
class RecommendLecturesTestCase(RecommendationServiceTestBase):
    """메인 추천 메서드 테스트"""

    def test_recommend_lectures_boundary_values(self) -> None:
        """top_n 경계값 테스트"""
        test_cases = [
            (0, "top_n=0"),
            (-5, "top_n=-5 (음수)"),
            (1000, "top_n=1000 (큰 값)"),
        ]

        for top_n, description in test_cases:
            with self.subTest(top_n=top_n, description=description):
                result = self.service.recommend_lectures(user_id=self.user1.id, top_n=top_n)
                self.assertIsNotNone(result, f"{description}: 결과가 None이 아니어야 합니다")

    def test_recommend_lectures_user_not_exists(self) -> None:
        """존재하지 않는 사용자 검증"""
        with self.assertRaisesMessage(ValueError, "User 99999 does not exist"):
            self.service.recommend_lectures(user_id=99999, top_n=10)

    def test_recommend_lectures_invalid_user_id_type(self) -> None:
        """잘못된 user_id 타입 검증"""
        with self.assertRaisesMessage(ValueError, "Invalid user_id"):
            self.service.recommend_lectures(user_id="invalid", top_n=10)  # type: ignore

    def test_recommend_lectures_model_not_loaded(self) -> None:
        """모델 로드 실패 시 폴백"""
        with mock.patch.object(self.service, "_ensure_model_loaded", return_value=False):
            result = self.service.recommend_lectures(user_id=self.user1.id, top_n=10)
            self.assertIsNotNone(result, "결과가 None이 아니어야 합니다")
            self.assertIsInstance(result, type(CrawledLecture.objects.none()))

    def test_recommend_lectures_user_not_in_model(self) -> None:
        """사용자가 모델에 없을 때 폴백"""
        with self._mock_als_environment(self.user1.id):
            with mock.patch.object(self.service, "_user_to_idx", {}):
                result = self.service.recommend_lectures(user_id=self.user1.id, top_n=10)
                self.assertIsNotNone(result, "결과가 None이 아니어야 합니다")

    def test_recommend_lectures_als_failure(self) -> None:
        """ALS 추천 실패 시 폴백"""

        def setup_failure(model: Any) -> None:
            model.recommend.side_effect = Exception("ALS failed")

        with self._mock_als_environment(self.user1.id, setup_failure):
            result = self.service.recommend_lectures(user_id=self.user1.id, top_n=10)
            self.assertIsNotNone(result, "결과가 None이 아니어야 합니다")

    def test_recommend_lectures_empty_result(self) -> None:
        """추천 결과가 완전히 비어있을 때"""

        def setup_empty(model: Any) -> None:
            model.recommend.return_value = (np.array([]), np.array([]))

        with self._mock_als_environment(self.user1.id, setup_empty):
            result = self.service.recommend_lectures(user_id=self.user1.id, top_n=10)
            self.assertIsNotNone(result, "결과가 None이 아니어야 합니다")

    def test_recommend_lectures_partial_results(self) -> None:
        """추천 결과가 요청보다 적을 때"""

        def setup_partial(model: Any) -> None:
            model.recommend.return_value = (np.array([0, 1]), np.array([0.9, 0.8]))

        with self._mock_als_environment(self.user1.id, setup_partial):
            with mock.patch.object(self.service, "_lecture_idx_to_id", {0: self.lecture1.id, 1: self.lecture2.id}):
                result = self.service.recommend_lectures(user_id=self.user1.id, top_n=10)
                self.assertIsNotNone(result, "결과가 None이 아니어야 합니다")
                self.assertLessEqual(result.count(), 10, "최대 10개의 결과를 반환해야 합니다")


# ========================================
# 8. 캐시 TTL 및 무효화 테스트
# ========================================
class CacheTTLTestCase(RecommendationServiceTestBase):
    """캐시 TTL 및 무효화 테스트"""

    def test_cache_ttl_expiration(self) -> None:
        """캐시 TTL 만료 테스트"""
        test_key = f"{self.cache_prefix}test_ttl_key"
        test_value = {"data": "test"}

        # Given: 0.01초 TTL로 캐시 저장
        cache.set(test_key, test_value, timeout=0.001)

        # When: TTL 만료 전 조회
        result = cache.get(test_key)
        self.assertEqual(result, test_value, "TTL 만료 전에는 값이 반환되어야 합니다")

        # When: TTL 만료 후 조회 (0.02초 대기)
        time.sleep(0.002)
        result = cache.get(test_key)

        # Then: None 반환
        self.assertIsNone(result, "TTL 만료 후에는 None이 반환되어야 합니다")

    def test_cache_invalidation_on_model_update(self) -> None:
        """모델 업데이트 시 캐시 무효화 테스트"""
        # 프로세스별 키 사용
        model_key = f"{self.cache_prefix}{ALS_MODEL_CACHE_KEY}"
        u_idx_key = f"{self.cache_prefix}{U_TO_IDX_CACHE_KEY}"
        l_idx_key = f"{self.cache_prefix}{L_TO_IDX_CACHE_KEY}"

        cache.set(model_key, {"test": "data"})
        cache.set(u_idx_key, {"test": 1})
        cache.set(l_idx_key, {"test": 1})

        cache.delete(model_key)
        cache.delete(u_idx_key)
        cache.delete(l_idx_key)

        self.assertIsNone(cache.get(model_key), "ALS 모델 캐시가 삭제되어야 합니다")
        self.assertIsNone(cache.get(u_idx_key), "사용자 인덱스 캐시가 삭제되어야 합니다")
        self.assertIsNone(cache.get(l_idx_key), "강의 인덱스 캐시가 삭제되어야 합니다")


# ========================================
# 9. Redis 통합 테스트
# ========================================
@unittest.skipUnless(hasattr(cache, "client") and hasattr(cache.client, "get_client"), "Redis backend not configured")
class RedisIntegrationTestCase(RecommendationServiceTestBase):
    """Redis 통합 테스트 (실제 Redis 사용)"""

    def test_full_recommendation_flow_with_redis(self) -> None:
        """전체 추천 플로우 end-to-end 테스트"""
        lecture3 = self._create_lecture(
            "테스트 강의 3",
            average_rating=4.8,
        )
        UserPreferCategory.objects.create(user=self.user1, category=self.category1)

        result = self.service.recommend_lectures(user_id=self.user1.id, top_n=5)

        self.assertIsNotNone(result, "결과가 None이 아니어야 합니다")
        self.assertLessEqual(result.count(), 5, "최대 5개의 결과를 반환해야 합니다")

        categories = self.service._get_user_prefer_categories(self.user1.id)
        self.assertIsNotNone(categories, "카테고리가 캐시되어야 합니다")
        self.assertGreater(len(categories), 0, "최소 1개의 카테고리가 있어야 합니다")

        cached_categories = cache.get(f"user_prefer_cats_{self.user1.id}")
        self.assertIsNotNone(cached_categories, "카테고리가 캐시에 있어야 합니다")

    def test_redis_pipeline_metadata_bulk_load(self) -> None:
        """Redis pipeline을 사용한 메타데이터 일괄 로드"""
        lectures = CrawledLecture.objects.bulk_create(
            [
                CrawledLecture(
                    title=f"강의 {i}",
                    instructor=f"강사 {i}",
                    average_rating=4.0 + (i * 0.1),
                    duration=300 + (i * 10),
                    difficulty="NORMAL",
                    description=f"설명 {i}",
                    platform="INFLEARN",
                    url_link=f"https://test.com/lecture{i}",
                )
                for i in range(10)
            ]
        )
        lecture_ids = [lec.id for lec in lectures]

        result = self.service._get_lectures_metadata_bulk(lecture_ids)

        self.assertEqual(len(result), 10, "10개 강의의 메타데이터를 반환해야 합니다")
        for lec_id in lecture_ids:
            self.assertIn(lec_id, result, f"강의 {lec_id}가 결과에 있어야 합니다")
            rating, cats = result[lec_id]
            self.assertIsInstance(rating, float, "평점은 float 타입이어야 합니다")
            self.assertIsInstance(cats, set, "카테고리는 set 타입이어야 합니다")
