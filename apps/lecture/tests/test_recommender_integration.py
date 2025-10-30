from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Dict, List, Tuple
from unittest.mock import Mock, patch

import numpy as np
from django.core.cache import cache
from implicit.als import AlternatingLeastSquares  # type: ignore
from scipy.sparse import csr_matrix

from apps.core.utils.isolated_cache_testcase import IsolatedRedisTestClient
from apps.lecture.models import (
    Category,
    CrawledLecture,
    LectureBookmark,
    LectureCategory,
    UserPreferCategory,
)
from apps.lecture.services.recommendation_service.constants import (
    ALS_MODEL_CACHE_KEY,
    L_IDX_TO_ID_CACHE_KEY,
    L_TO_IDX_CACHE_KEY,
    LECTURE_METADATA_CACHE_KEY,
    U_TO_IDX_CACHE_KEY,
    USER_ITEMS_MATRIX_CACHE_KEY,
)
from apps.lecture.services.recommendation_service.recommender import (
    RecommendationService,
)
from apps.users.enums import Gender
from apps.users.models import User


class RecommendationServiceIntegrationTest(IsolatedRedisTestClient):
    """RecommendationService 통합 테스트 - 실제 DB와 격리된 Redis 캐시 사용"""

    user1: User
    user2: User
    user3: User
    category_python: Category
    category_django: Category
    category_web: Category
    lecture1: CrawledLecture
    lecture2: CrawledLecture
    lecture3: CrawledLecture
    lecture4: CrawledLecture
    service: RecommendationService

    @classmethod
    def setUpTestData(cls) -> None:
        """테스트 데이터 생성"""
        users = User.objects.bulk_create(
            [
                User(
                    email="user1@example.com",
                    nickname="user1",
                    name="User One",
                    phone_number="010-1111-1111",
                    birthday=date(1990, 1, 1),
                    gender=Gender.MALE,
                    is_active=True,
                ),
                User(
                    email="user2@example.com",
                    nickname="user2",
                    name="User Two",
                    phone_number="010-2222-2222",
                    birthday=date(1991, 2, 2),
                    gender=Gender.FEMALE,
                    is_active=True,
                ),
                User(
                    email="user3@example.com",
                    nickname="user3",
                    name="User Three",
                    phone_number="010-3333-3333",
                    birthday=date(1992, 3, 3),
                    gender=Gender.MALE,
                    is_active=True,
                ),
            ]
        )
        cls.user1, cls.user2, cls.user3 = users

        categories = Category.objects.bulk_create(
            [
                Category(name="Python Programming"),
                Category(name="Django Framework"),
                Category(name="Web Development"),
            ]
        )
        cls.category_python, cls.category_django, cls.category_web = categories

        lectures = CrawledLecture.objects.bulk_create(
            [
                CrawledLecture(
                    title="Django Tutorial for Beginners",
                    instructor="John Doe",
                    average_rating=Decimal("4.50"),
                    duration=120,
                    difficulty=CrawledLecture.DifficultyEnum.EASY,
                    description="Learn Django from scratch",
                    platform=CrawledLecture.PlatformEnum.UDEMY,
                    original_price=50000,
                    discount_price=30000,
                    url_link="https://example.com/django-tutorial",
                ),
                CrawledLecture(
                    title="Advanced Python Programming",
                    instructor="Jane Smith",
                    average_rating=Decimal("4.80"),
                    duration=180,
                    difficulty=CrawledLecture.DifficultyEnum.HARD,
                    description="Master Python",
                    platform=CrawledLecture.PlatformEnum.UDEMY,
                    original_price=80000,
                    discount_price=60000,
                    url_link="https://example.com/python-advanced",
                ),
                CrawledLecture(
                    title="Web Development Bootcamp",
                    instructor="Bob Johnson",
                    average_rating=Decimal("4.20"),
                    duration=240,
                    difficulty=CrawledLecture.DifficultyEnum.NORMAL,
                    description="Full-stack web development",
                    platform=CrawledLecture.PlatformEnum.UDEMY,
                    original_price=100000,
                    discount_price=70000,
                    url_link="https://example.com/web-bootcamp",
                ),
                CrawledLecture(
                    title="Python for Data Science",
                    instructor="Alice Brown",
                    average_rating=Decimal("4.60"),
                    duration=150,
                    difficulty=CrawledLecture.DifficultyEnum.EASY,
                    description="Data science with Python",
                    platform=CrawledLecture.PlatformEnum.INFLEARN,
                    original_price=70000,
                    discount_price=50000,
                    url_link="https://example.com/python-data-science",
                ),
            ]
        )
        cls.lecture1, cls.lecture2, cls.lecture3, cls.lecture4 = lectures

        # 강의-카테고리 매핑
        LectureCategory.objects.bulk_create(
            [
                LectureCategory(lecture=cls.lecture1, category=cls.category_django),
                LectureCategory(lecture=cls.lecture1, category=cls.category_web),
                LectureCategory(lecture=cls.lecture2, category=cls.category_python),
                LectureCategory(lecture=cls.lecture3, category=cls.category_web),
                LectureCategory(lecture=cls.lecture4, category=cls.category_python),
            ]
        )

        # 사용자 선호 카테고리
        UserPreferCategory.objects.bulk_create(
            [
                UserPreferCategory(user=cls.user1, category=cls.category_django),
                UserPreferCategory(user=cls.user1, category=cls.category_python),
                UserPreferCategory(user=cls.user2, category=cls.category_web),
            ]
        )

        # 북마크
        LectureBookmark.objects.bulk_create(
            [
                LectureBookmark(user=cls.user1, lecture=cls.lecture1),
                LectureBookmark(user=cls.user2, lecture=cls.lecture3),
            ]
        )

    def setUp(self) -> None:
        """각 테스트 전 초기화"""
        super().setUp()
        cache.clear()

        # RecommendationService 인스턴스 생성
        self.service = RecommendationService()

    def tearDown(self) -> None:
        """각 테스트 후 정리"""
        cache.clear()
        super().tearDown()

    def _create_mock_model(
        self,
    ) -> Tuple[AlternatingLeastSquares, Dict[int, int], Dict[int, int], csr_matrix]:
        """Mock ALS 모델 생성"""
        user_ids: List[int] = [self.user1.id, self.user2.id]
        lecture_ids: List[int] = [self.lecture1.id, self.lecture2.id, self.lecture3.id]

        # NumPy 배열로 명시적 변환
        rows_array: np.ndarray = np.array([0, 0, 1], dtype=np.int32)
        cols_array: np.ndarray = np.array([0, 1, 2], dtype=np.int32)
        data_array: np.ndarray = np.array([1.0, 0.5, 0.8], dtype=np.float32)

        # csr_matrix 생성 - 타입 추론용 분리
        matrix: csr_matrix = csr_matrix(
            (data_array, (rows_array, cols_array)),
            shape=(len(user_ids), len(lecture_ids)),
            dtype=np.float32,
        )

        u_to_idx: Dict[int, int] = {uid: i for i, uid in enumerate(user_ids)}
        l_to_idx: Dict[int, int] = {lid: i for i, lid in enumerate(lecture_ids)}

        model: AlternatingLeastSquares = AlternatingLeastSquares(
            factors=10,
            regularization=0.01,
            iterations=5,
        )
        model.fit(matrix.T)

        return model, u_to_idx, l_to_idx, matrix

    def test_redis_health_check(self) -> None:
        """Redis 헬스체크 테스트"""
        # Redis 연결 상태 확인
        is_healthy = self.service._check_redis_health(log_status=False)

        # Redis가 사용 가능한지 확인
        self.assertIsInstance(is_healthy, bool)

        # _is_redis_ready 메서드 테스트
        is_ready = self.service._is_redis_ready()
        self.assertIsInstance(is_ready, bool)

    def test_cache_get_set_safe_django_backend(self) -> None:
        """Django 캐시 백엔드: 안전한 get/set 테스트"""
        test_key = "test_key"
        test_value = {"data": "test_data", "number": 123}

        # 저장
        self.service._cache_set_safe(test_key, test_value, timeout=60, backend="django")

        # 조회
        retrieved = self.service._cache_get_safe(test_key, backend="django")

        # 검증
        self.assertEqual(retrieved, test_value)

    def test_cache_get_set_safe_redis_backend(self) -> None:
        """Redis 캐시 백엔드: 안전한 get/set 테스트"""
        if not self.service._is_redis_ready():
            self.skipTest("Redis not available")

        test_key = "test_redis_key"
        test_value = {"data": "redis_test", "list": [1, 2, 3]}

        # 저장
        self.service._cache_set_safe(test_key, test_value, timeout=60, backend="redis")

        # 조회
        retrieved = self.service._cache_get_safe(test_key, backend="redis")

        # 검증
        self.assertEqual(retrieved, test_value)

    def test_cache_serialization_error_handling(self) -> None:
        """캐시 직렬화 에러 처리 테스트"""
        test_key = "test_error_key"

        # 직렬화 불가능한 객체 (예: lambda)
        with patch("pickle.dumps", side_effect=Exception("Serialization error")):
            # 에러가 발생해도 프로세스는 계속되어야 함
            self.service._cache_set_safe(test_key, {"data": "test"}, timeout=60, backend="django")

            # 조회 시 None 반환
        result = self.service._cache_get_safe(test_key, backend="django")
        self.assertIsNone(result)

    def test_metadata_get_set_safe(self) -> None:
        """강의 메타데이터 캐시 get/set 테스트"""
        cache_key = LECTURE_METADATA_CACHE_KEY.format(self.lecture1.id)
        avg_rating = 4.5
        category_ids = {self.category_django.id, self.category_web.id}

        # 저장
        self.service._metadata_set_safe(cache_key, avg_rating, category_ids)

        # 조회
        metadata = self.service._metadata_get_safe(cache_key)

        # 검증
        self.assertIsNotNone(metadata)
        assert metadata is not None
        retrieved_rating, retrieved_cats = metadata
        self.assertEqual(retrieved_rating, avg_rating)
        self.assertEqual(retrieved_cats, category_ids)

    def test_load_from_redis_success(self) -> None:
        """캐시에서 모델 로드 성공 테스트"""
        # Mock 모델 생성
        model, u_to_idx, l_to_idx, matrix = self._create_mock_model()
        l_idx_to_id = {v: k for k, v in l_to_idx.items()}

        # 캐시에 저장
        backend = "redis" if self.service._is_redis_ready() else "django"
        self.service._cache_set_safe(ALS_MODEL_CACHE_KEY, model, 3600, backend=backend)
        self.service._cache_set_safe(U_TO_IDX_CACHE_KEY, u_to_idx, 3600, backend=backend)
        self.service._cache_set_safe(L_TO_IDX_CACHE_KEY, l_to_idx, 3600, backend=backend)
        self.service._cache_set_safe(L_IDX_TO_ID_CACHE_KEY, l_idx_to_id, 3600, backend=backend)
        self.service._cache_set_safe(USER_ITEMS_MATRIX_CACHE_KEY, matrix, 3600, backend=backend)

        # 로드
        result = self.service._load_from_redis()

        # 검증
        self.assertTrue(result)
        self.assertIsNotNone(self.service._model)
        self.assertIsNotNone(self.service._user_to_idx)
        self.assertIsNotNone(self.service._lecture_to_idx)

    def test_load_from_redis_partial_data(self) -> None:
        """캐시에 부분 데이터만 있을 때 로드 실패 테스트"""
        # 일부 데이터만 캐시에 저장
        backend = "redis" if self.service._is_redis_ready() else "django"
        model, u_to_idx, l_to_idx, matrix = self._create_mock_model()

        # 모델만 저장하고 나머지는 저장하지 않음
        self.service._cache_set_safe(ALS_MODEL_CACHE_KEY, model, 3600, backend=backend)

        # 로드 시도
        result = self.service._load_from_redis()

        # 부분 데이터만 있으므로 로드 실패
        self.assertFalse(result)
        self.assertIsNone(self.service._model)

    def test_get_category_fallback(self) -> None:
        """카테고리 기반 폴백 추천 테스트"""
        # 기존 UserPreferCategory 삭제 또는 get_or_create 사용
        UserPreferCategory.objects.filter(user=self.user1, category=self.category_python).delete()

        # 새로 생성
        UserPreferCategory.objects.create(user=self.user1, category=self.category_python)

        # 폴백 추천 조회
        qs = self.service._get_category_fallback(self.user1.id, top_n=5)

        # 검증: 결과가 있는지 확인
        self.assertGreater(qs.count(), 0)

        lecture_ids = list(qs.values_list("id", flat=True))

        # lecture1이 category_python과 실제로 연결되어 있는지 확인
        lecture1_categories = set(
            LectureCategory.objects.filter(lecture=self.lecture1).values_list("category_id", flat=True)
        )

        # lecture1이 category_python과 연결되어 있다면 추천 결과에 포함되어야 함
        if self.category_python.id in lecture1_categories:
            self.assertIn(self.lecture1.id, lecture_ids)
        else:
            # 연결되어 있지 않다면, 최소한 category_python 카테고리의 강의가 반환되어야 함
            returned_lecture_categories = set(
                LectureCategory.objects.filter(lecture_id__in=lecture_ids).values_list("category_id", flat=True)
            )
            self.assertIn(self.category_python.id, returned_lecture_categories)

    def test_recommend_lectures_with_als(self) -> None:
        """ALS 모델을 사용한 추천 테스트"""
        # Mock 모델 설정
        model, u_to_idx, l_to_idx, matrix = self._create_mock_model()
        l_idx_to_id = {v: k for k, v in l_to_idx.items()}

        self.service._model = model
        self.service._user_to_idx = u_to_idx
        self.service._lecture_to_idx = l_to_idx
        self.service._lecture_idx_to_id = l_idx_to_id
        self.service._user_items_matrix = matrix

        # 추천 조회
        qs = self.service.recommend_lectures(self.user1.id, top_n=5)

        # 검증
        self.assertIsNotNone(qs)
        self.assertGreater(qs.count(), 0)
        self.assertLessEqual(qs.count(), 5)

    def test_recommend_lectures_fallback_to_category(self) -> None:
        """ALS 모델 없을 때 카테고리 폴백 테스트"""
        # 모델 없음
        self.service._model = None

        # get_or_create로 중복 방지
        UserPreferCategory.objects.get_or_create(user=self.user1, category=self.category_python)

        # 추천 조회
        qs = self.service.recommend_lectures(self.user1.id, top_n=5)

        # 검증
        self.assertIsNotNone(qs)
        self.assertGreater(qs.count(), 0)

    def test_post_process_ranking_with_category_bonus(self) -> None:
        """카테고리 매칭 보너스 적용 테스트"""
        UserPreferCategory.objects.get_or_create(user=self.user1, category=self.category_python)

        # Mock 추천 결과
        recommended_idx_scores = [(0, 0.5), (1, 0.4)]

        # Mock 모델 설정
        model, u_to_idx, l_to_idx, matrix = self._create_mock_model()
        l_idx_to_id = {v: k for k, v in l_to_idx.items()}

        self.service._lecture_idx_to_id = l_idx_to_id

        # 후처리 실행
        ranked_ids = self.service._get_post_processed_ranking(self.user1.id, recommended_idx_scores)

        # 검증
        self.assertGreater(len(ranked_ids), 0)

    def test_metadata_cache(self) -> None:
        """강의 메타데이터 캐싱 테스트"""
        lecture_ids: List[int] = [self.lecture1.id, self.lecture2.id, self.lecture3.id]

        metadata1 = self.service._get_lectures_metadata_bulk(lecture_ids)
        metadata2 = self.service._get_lectures_metadata_bulk(lecture_ids)

        self.assertEqual(metadata1, metadata2)
        self.assertIn(self.lecture1.id, metadata1)

        rating, categories = metadata1[self.lecture1.id]
        self.assertEqual(rating, float(self.lecture1.average_rating))

        # setUpTestData에서 실제로 생성된 카테고리 ID 확인
        # lecture1에 연결된 실제 카테고리 ID 가져오기
        actual_category_ids = set(
            LectureCategory.objects.filter(lecture=self.lecture1).values_list("category_id", flat=True)
        )

        # 반환된 categories가 실제 카테고리 ID의 부분집합인지 확인
        self.assertTrue(categories.issubset(actual_category_ids) or actual_category_ids.issubset(categories))

    def test_recommend_for_user_new_format_tuple(self) -> None:
        """ALS 추천: 튜플 형식 처리"""
        # Mock 모델 설정
        model, u_to_idx, l_to_idx, matrix = self._create_mock_model()
        l_idx_to_id: Dict[int, int] = {v: k for k, v in l_to_idx.items()}

        self.service._model = model
        self.service._user_to_idx = u_to_idx
        self.service._lecture_to_idx = l_to_idx
        self.service._lecture_idx_to_id = l_idx_to_id
        self.service._user_items_matrix = matrix

        # recommend() 메서드가 신버전 형식 반환하도록 mock
        indices = np.array([0, 1])
        scores = np.array([0.8, 0.6])
        model.recommend = Mock(return_value=(indices, scores))

        # 추천 실행
        qs = self.service.recommend_lectures(self.user1.id, top_n=5)

        # 검증
        self.assertGreater(qs.count(), 0)

    def test_recommend_for_user_unexpected_format(self) -> None:
        """ALS 추천: 예상치 못한 형식 처리 - 카테고리 폴백"""
        model, u_to_idx, l_to_idx, matrix = self._create_mock_model()
        l_idx_to_id: Dict[int, int] = {v: k for k, v in l_to_idx.items()}

        self.service._model = model
        self.service._user_to_idx = u_to_idx
        self.service._lecture_to_idx = l_to_idx
        self.service._lecture_idx_to_id = l_idx_to_id
        self.service._user_items_matrix = matrix

        UserPreferCategory.objects.filter(user=self.user1).delete()
        UserPreferCategory.objects.create(user=self.user1, category=self.category_python)

        # recommend() 메서드가 예상치 못한 형식 반환하도록 mock
        model.recommend = Mock(return_value="unexpected_string")

        # 추천 실행 - 카테고리 폴백으로 대체되어야 함
        qs = self.service.recommend_lectures(self.user1.id, top_n=5)

        # 검증: 카테고리 폴백 결과 반환
        self.assertGreater(qs.count(), 0)

    def test_recommend_for_user_empty_recommendations(self) -> None:
        """ALS 추천: 빈 추천 결과 - 카테고리 폴백"""
        # Mock 모델 설정
        model, u_to_idx, l_to_idx, matrix = self._create_mock_model()
        l_idx_to_id: Dict[int, int] = {v: k for k, v in l_to_idx.items()}

        self.service._model = model
        self.service._user_to_idx = u_to_idx
        self.service._lecture_to_idx = l_to_idx
        self.service._lecture_idx_to_id = l_idx_to_id
        self.service._user_items_matrix = matrix

        # 사용자 선호 카테고리 설정
        UserPreferCategory.objects.filter(user=self.user1).delete()
        UserPreferCategory.objects.create(user=self.user1, category=self.category_python)

        # recommend() 메서드가 빈 결과 반환하도록 mock
        model.recommend = Mock(return_value=(np.array([]), np.array([])))

        # 추천 실행 - 카테고리 폴백으로 대체되어야 함
        qs = self.service.recommend_lectures(self.user1.id, top_n=5)

        # 검증: 카테고리 폴백 결과 반환
        self.assertGreater(qs.count(), 0)

        # recommend() 메서드가 예상치 못한 형식 반환하도록 mock
        model.recommend = Mock(return_value="unexpected_string")

        # 추천 실행 - 카테고리 폴백으로 대체되어야 함
        qs = self.service.recommend_lectures(self.user1.id, top_n=5)

        # 검증: 카테고리 폴백 결과 반환
        self.assertGreater(qs.count(), 0)
