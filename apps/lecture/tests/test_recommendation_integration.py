import os
from datetime import date
from typing import Any, Dict, List

from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
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
from apps.lecture.tests.base_lecture import BaseLectureTest
from apps.users.models import User


@override_settings(ALS_MODEL_VERSION="test_v1.0.0")
class RecommendationViewIntegrationTest(IsolatedRedisTestClient, BaseLectureTest):
    """
    추천 API 통합 테스트
    """

    databases = {"default"}

    user: Any
    category_python: Category
    category_django: Category
    category_javascript: Category
    lecture3: CrawledLecture
    recommendation_url: str

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()

        # BaseLectureTest에서 생성된 카테고리 재사용
        cls.category_python = cls.category1  # "Python" 카테고리
        cls.category_django, _ = Category.objects.get_or_create(name="Django")
        cls.category_javascript, _ = Category.objects.get_or_create(name="JavaScript")

        # 추가 강의 생성
        cls.lecture3 = CrawledLecture.objects.create(
            title="JavaScript 기초",
            instructor="이영희",
            average_rating=4.3,
            duration=400,
            difficulty="EASY",
            description="JavaScript 기초 강의",
            platform="INFLEARN",
            original_price=40000,
            discount_price=25000,
            url_link="https://www.inflearn.com/javascript",
        )

        # 강의-카테고리 연결
        LectureCategory.objects.bulk_create(
            [
                LectureCategory(lecture=cls.lecture3, category=cls.category_javascript),
            ]
        )

        # 테스트 사용자 생성
        cls.user = User.objects.create_user(
            email="recommend_test@example.com",
            password="testpass123",
            nickname="recmnduser",
            name="추천테스트유저",
            phone_number="010-9999-9999",
            birthday=date(1995, 5, 15),
            gender="MALE",
        )

        cls.recommendation_url = reverse("recommendations")

    def setUp(self) -> None:
        """각 테스트 전 설정"""
        super().setUp()
        cache.clear()
        self.client.force_authenticate(user=self.user)

    def tearDown(self) -> None:
        """각 테스트 후 정리"""
        super().tearDown()
        if os.path.exists(MODEL_BUNDLE_PATH):
            os.remove(MODEL_BUNDLE_PATH)
        if os.path.exists(MODEL_BACKUP_PATH):
            os.remove(MODEL_BACKUP_PATH)

    def test_integration_new_user_receives_popular_recommendations(self) -> None:
        """신규 사용자는 인기 강의 추천 받음"""
        response: Response = self.client.get(self.recommendation_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data), 0, "추천 결과가 비어있음")

        # 응답 구조 검증
        first_lecture: Dict[str, Any] = response.data[0]
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
            "duration",
            "url_link",
            "is_bookmarked",
        ]

        for field in required_fields:
            self.assertIn(field, first_lecture, f"필수 필드 '{field}'가 응답에 없음")

    def test_integration_user_with_preferences_receives_personalized_recommendations(self) -> None:
        """선호 카테고리가 있는 사용자는 개인화된 추천 받음"""
        UserPreferCategory.objects.create(user=self.user, category=self.category_python)

        response: Response = self.client.get(self.recommendation_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data), 0, "추천 결과가 비어있음")

    def test_integration_bookmarked_lectures_excluded_from_recommendations(self) -> None:
        """북마크된 강의는 추천에서 제외됨"""
        LectureBookmark.objects.create(user=self.user, lecture=self.lecture1)

        response: Response = self.client.get(self.recommendation_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        lecture_ids: List[int] = [lec["id"] for lec in response.data]
        self.assertNotIn(self.lecture1.id, lecture_ids, "북마크된 강의는 제외되어야 함")

    def test_integration_unauthenticated_user_cannot_access_recommendations(self) -> None:
        """인증되지 않은 사용자는 추천 접근 불가"""
        self.client.force_authenticate(user=None)
        response: Response = self.client.get(self.recommendation_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_integration_cache_hit_for_repeated_requests(self) -> None:
        """반복 요청 시 캐시 히트 확인"""
        response1: Response = self.client.get(self.recommendation_url)
        response2: Response = self.client.get(self.recommendation_url)

        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertEqual(response1.data, response2.data, "캐시된 결과가 동일해야 함")

    def test_integration_multiple_bookmarks_excluded(self) -> None:
        """여러 북마크가 모두 추천에서 제외됨"""
        LectureBookmark.objects.bulk_create(
            [
                LectureBookmark(user=self.user, lecture=self.lecture1),
                LectureBookmark(user=self.user, lecture=self.lecture3),
            ]
        )

        response: Response = self.client.get(self.recommendation_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        lecture_ids: List[int] = [lec["id"] for lec in response.data]
        self.assertNotIn(self.lecture1.id, lecture_ids, "북마크된 강의는 제외되어야 함")
        self.assertNotIn(self.lecture3.id, lecture_ids, "북마크된 강의는 제외되어야 함")

    def test_integration_full_model_training_and_recommendation_flow(self) -> None:
        """
        모델 학습 → 저장 → 로드 → 추천 생성 전체 플로우

        테스트 범위: ModelTrainer → RecommendationService → API
        """
        LectureBookmark.objects.bulk_create(
            [
                LectureBookmark(user=self.user, lecture=self.lecture1),
                LectureBookmark(user=self.user, lecture=self.lecture2),
            ]
        )

        data_loader = DataLoader()
        trainer = ModelTrainer(data_loader=data_loader)
        success = trainer.train_and_save_full_model()

        self.assertTrue(success, "모델 학습 및 저장 실패")

        response: Response = self.client.get(self.recommendation_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data), 0, "추천 결과가 비어있음")
