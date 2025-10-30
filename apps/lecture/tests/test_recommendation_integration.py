import os
import time
from datetime import date
from typing import Any, Dict, List

from django.core.cache import cache
from django.db import IntegrityError
from django.test import override_settings
from rest_framework import status
from rest_framework.response import Response

from apps.core.utils.isolated_cache_testcase import IsolatedRedisTestClient
from apps.lecture.models import (
    Category,
    CrawledLecture,
    LectureBookmark,
    LectureCategory,
    UserPreferCategory,
)
from apps.lecture.services.recommendation_service.data_loader import DataLoader
from apps.lecture.services.recommendation_service.model_trainer import (
    MODEL_BACKUP_PATH,
    MODEL_BUNDLE_PATH,
    ModelTrainer,
)
from apps.users.enums import Gender
from apps.users.models import User


@override_settings(ALS_MODEL_VERSION="test_v1.0.0")
class RecommendationViewIntegrationTest(IsolatedRedisTestClient):
    """
    추천 API 통합 테스트

    통합 테스트 범위:
    - API 엔드포인트 → RecommendationService → DataLoader/ModelTrainer → Database
    - 캐시 시스템 (Redis/Django Cache)
    - 전체 추천 플로우 (ALS → 카테고리 기반 → 인기 강의 폴백)
    """

    databases = {"default"}

    user: User
    category_python: Category
    category_django: Category
    lecture1: CrawledLecture
    lecture2: CrawledLecture
    lecture3: CrawledLecture

    @classmethod
    def setUpClass(cls) -> None:
        """테스트 클래스 초기화 및 이전 모델 파일 정리"""
        super().setUpClass()

        os.environ["ALS_MODEL_VERSION"] = "test_v1.0.0"

        if os.path.exists(MODEL_BUNDLE_PATH):
            os.remove(MODEL_BUNDLE_PATH)
        if os.path.exists(MODEL_BACKUP_PATH):
            os.remove(MODEL_BACKUP_PATH)

    @classmethod
    def tearDownClass(cls) -> None:
        """테스트 클래스 정리"""
        if "ALS_MODEL_VERSION" in os.environ:
            del os.environ["ALS_MODEL_VERSION"]
        super().tearDownClass()

    @classmethod
    def setUpTestData(cls) -> None:
        """테스트 데이터 설정 (클래스 레벨에서 한 번만 실행)"""
        cls.user = User.objects.create_user(
            email="testuser@example.com",
            password="testpass123",
            nickname="테스터",
            name="홍길동",
            phone_number="010-1234-5678",
            birthday=date(1990, 1, 1),
            gender=Gender.MALE,
        )
        cls.user.is_active = True
        cls.user.save()

        categories = Category.objects.bulk_create(
            [
                Category(name="Python"),
                Category(name="Django"),
            ]
        )
        cls.category_python, cls.category_django = categories

        lectures = CrawledLecture.objects.bulk_create(
            [
                CrawledLecture(
                    title="Python 기초",
                    instructor="김강사",
                    average_rating=4.5,
                    duration=600,
                    difficulty=CrawledLecture.DifficultyEnum.EASY,
                    description="Python 기초 강의",
                    platform=CrawledLecture.PlatformEnum.UDEMY,
                    original_price=100000,
                    discount_price=50000,
                    url_link="https://example.com/python",
                ),
                CrawledLecture(
                    title="Django 심화",
                    instructor="이강사",
                    average_rating=4.8,
                    duration=900,
                    difficulty=CrawledLecture.DifficultyEnum.NORMAL,
                    description="Django 심화 강의",
                    platform=CrawledLecture.PlatformEnum.INFLEARN,
                    original_price=150000,
                    discount_price=75000,
                    url_link="https://example.com/django",
                ),
                CrawledLecture(
                    title="Python 고급",
                    instructor="박강사",
                    average_rating=4.7,
                    duration=1200,
                    difficulty=CrawledLecture.DifficultyEnum.HARD,
                    description="Python 고급 강의",
                    platform=CrawledLecture.PlatformEnum.UDEMY,
                    original_price=200000,
                    discount_price=100000,
                    url_link="https://example.com/python-advanced",
                ),
            ]
        )
        cls.lecture1, cls.lecture2, cls.lecture3 = lectures

        LectureCategory.objects.bulk_create(
            [
                LectureCategory(lecture=cls.lecture1, category=cls.category_python),
                LectureCategory(lecture=cls.lecture2, category=cls.category_django),
                LectureCategory(lecture=cls.lecture3, category=cls.category_python),
            ]
        )

        UserPreferCategory.objects.create(user=cls.user, category=cls.category_python)

    def setUp(self) -> None:
        """각 테스트 전 설정"""
        cache.clear()

    def tearDown(self) -> None:
        """각 테스트 후 정리"""
        cache.clear()

    # ==================== 기본 추천 플로우 통합 테스트 ====================

    def test_integration_recommendation_api_returns_lectures(self) -> None:
        """
        추천 API가 강의 목록을 반환

        테스트 범위: API → Service → DB
        """
        # When: 추천 API 호출
        self.client.force_authenticate(user=self.user)
        response: Response = self.client.get("/api/v1/lectures/recommendations")

        # Then: 정상 응답 및 리스트 반환
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)

    def test_integration_model_version_consistency(self) -> None:
        """
        테스트 환경에서 모델 버전 유지

        테스트 범위: 환경변수 → Service
        """
        # When: 환경변수 확인
        test_version = os.environ.get("ALS_MODEL_VERSION")

        # Then: 테스트 버전 일관성 확인
        self.assertIsNotNone(test_version, "ALS_MODEL_VERSION 환경변수가 설정되어야 함")
        self.assertEqual(test_version, "test_v1.0.0")

        # When: 추천 API 호출
        self.client.force_authenticate(user=self.user)
        response: Response = self.client.get("/api/v1/lectures/recommendations")

        # Then: 정상 응답 (버전 일관성 유지)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # ==================== 인증 및 권한 통합 테스트 ====================

    def test_integration_unauthenticated_user_cannot_access_recommendations(self) -> None:
        """
        인증되지 않은 사용자는 추천 API 접근 불가

        테스트 범위: API → Authentication Middleware
        """
        # When: 인증 없이 API 호출
        response: Response = self.client.get("/api/v1/lectures/recommendations")

        # Then: 401 Unauthorized
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_integration_authenticated_user_can_access_recommendations(self) -> None:
        """
        인증된 사용자는 추천 API 접근 가능

        테스트 범위: API → Authentication → Service
        """
        # When: 인증 후 API 호출
        self.client.force_authenticate(user=self.user)
        response: Response = self.client.get("/api/v1/lectures/recommendations")

        # Then: 200 OK
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # ==================== 데이터 일관성 통합 테스트 ====================

    def test_integration_response_structure_contains_all_required_fields(self) -> None:
        """
        추천 API 응답이 모든 필수 필드를 포함

        테스트 범위: API → Service → Serializer
        """
        # When: 추천 API 호출
        self.client.force_authenticate(user=self.user)
        response: Response = self.client.get("/api/v1/lectures/recommendations")

        # Then: 응답 구조 검증
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        if len(response.data) > 0:
            lecture: Dict[str, Any] = response.data[0]
            required_fields: List[str] = [
                "id",
                "uuid",
                "title",
                "instructor",
                "thumbnail_img_url",
                "categories",
                "difficulty",
                "original_price",
                "discount_price",
                "platform",
                "average_rating",
                "url_link",
                "is_bookmarked",
            ]

            for field in required_fields:
                self.assertIn(field, lecture, f"필수 필드 '{field}'가 응답에 없음")

    def test_integration_bookmarked_lectures_excluded_from_recommendations(self) -> None:
        """
        북마크된 강의는 추천에서 제외됨

        테스트 범위: API → Service → DataLoader → DB
        """
        # Given: lecture1 북마크
        LectureBookmark.objects.create(user=self.user, lecture=self.lecture1)

        # When: 추천 API 호출
        self.client.force_authenticate(user=self.user)
        response: Response = self.client.get("/api/v1/lectures/recommendations")

        # Then: 북마크된 강의 제외 확인
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        lecture_ids: List[int] = [lec["id"] for lec in response.data]
        self.assertNotIn(self.lecture1.id, lecture_ids, "북마크된 강의는 추천에서 제외되어야 함")

        # ==================== 폴백 전략 통합 테스트 ====================

    def test_integration_category_based_fallback_when_no_model(self) -> None:
        """
        모델 없을 때 카테고리 기반 폴백 작동

        테스트 범위: API → Service (폴백 로직) → DB
        """
        # Given: 캐시 초기화 (모델 없는 상태)
        cache.clear()

        # When: 추천 API 호출
        self.client.force_authenticate(user=self.user)
        response: Response = self.client.get("/api/v1/lectures/recommendations")

        # Then: 카테고리 기반 추천 작동
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)

    def test_integration_popular_lectures_fallback_when_no_preferences(self) -> None:
        """
        선호 카테고리 없을 때 인기 강의 폴백 작동

        테스트 범위: API → Service (폴백 로직) → DB
        """
        # Given: 선호 카테고리 삭제
        UserPreferCategory.objects.filter(user=self.user).delete()
        cache.clear()

        # When: 추천 API 호출
        self.client.force_authenticate(user=self.user)
        response: Response = self.client.get("/api/v1/lectures/recommendations")

        # Then: 인기 강의 폴백 작동
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)

        # ==================== DB 제약조건 통합 테스트 ====================

    def test_integration_duplicate_bookmark_raises_integrity_error(self) -> None:
        """
        통합: 중복 북마크 생성 시 IntegrityError 발생

        테스트 범위: DB Constraint
        """
        # Given: lecture1 북마크 생성
        LectureBookmark.objects.create(user=self.user, lecture=self.lecture1)

        # When, Then: 동일한 북마크 재생성 시 IntegrityError
        with self.assertRaises(IntegrityError):
            LectureBookmark.objects.create(user=self.user, lecture=self.lecture1)

    def test_integration_duplicate_prefer_category_raises_integrity_error(self) -> None:
        """
        중복 선호 카테고리 생성 시 IntegrityError 발생

        테스트 범위: DB Constraint
        """
        # When, Then: 동일한 선호 카테고리 재생성 시 IntegrityError
        with self.assertRaises(IntegrityError):
            UserPreferCategory.objects.create(user=self.user, category=self.category_python)

    # ==================== 전체 플로우 통합 테스트 ====================

    def test_integration_full_recommendation_flow_with_interactions(self) -> None:
        """
        사용자 상호작용 → 추천 생성 전체 플로우

        테스트 범위: API → Service → DataLoader → ModelTrainer → DB
        """
        # Given: 사용자 상호작용 생성
        LectureBookmark.objects.bulk_create(
            [
                LectureBookmark(user=self.user, lecture=self.lecture2),
                LectureBookmark(user=self.user, lecture=self.lecture3),
            ]
        )

        # When: 추천 API 호출
        self.client.force_authenticate(user=self.user)
        response: Response = self.client.get("/api/v1/lectures/recommendations")

        # Then: 추천 결과 반환 및 북마크 제외 확인
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)

        lecture_ids: List[int] = [lec["id"] for lec in response.data]
        self.assertNotIn(self.lecture2.id, lecture_ids, "북마크된 강의는 제외되어야 함")
        self.assertNotIn(self.lecture3.id, lecture_ids, "북마크된 강의는 제외되어야 함")

    def test_integration_full_model_training_and_recommendation_flow(self) -> None:
        """
        모델 학습 → 저장 → 로드 → 추천 생성 전체 플로우

        테스트 범위: ModelTrainer → RecommendationService → API
        """
        # Given: 사용자 상호작용 생성
        LectureBookmark.objects.bulk_create(
            [
                LectureBookmark(user=self.user, lecture=self.lecture1),
                LectureBookmark(user=self.user, lecture=self.lecture2),
            ]
        )

        # When: 모델 학습 및 저장
        data_loader = DataLoader()
        trainer = ModelTrainer(data_loader=data_loader)
        success = trainer.train_and_save_full_model()

        # Then: 학습 성공 확인
        self.assertTrue(success, "모델 학습 및 저장 실패")

        # When: 추천 API 호출
        self.client.force_authenticate(user=self.user)
        response: Response = self.client.get("/api/v1/lectures/recommendations")

        # Then: ALS 기반 추천 작동 확인
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data), 0, "추천 결과가 비어있음")
