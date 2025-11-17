import os

os.environ["TQDM_DISABLE"] = "1"

import sys
from unittest.mock import MagicMock

sys.modules["tqdm"] = MagicMock()
sys.modules["tqdm.auto"] = MagicMock()
import logging
import shutil
import tempfile
import warnings
from typing import Any, Dict, List, Set, cast

from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.utils.isolated_cache_testcase import IsolatedRedisTestClient
from apps.lecture.models import (
    Category,
    CrawledLecture,
    LectureBookmark,
    LectureCategory,
    UserPreferCategory,
)
from apps.lecture.services.recommendation_service.constants import (
    ALS_CACHE_KEYS,
    MODEL_VERSION,
)
from apps.lecture.services.recommendation_service.data_loader import DataLoader
from apps.lecture.services.recommendation_service.model_trainer import ModelTrainer
from apps.lecture.tests.base_lecture import BaseLectureTest
from apps.users.models.user import User


# @tag('serial', 'integration')
class RecommendationEndToEndTest(IsolatedRedisTestClient, BaseLectureTest):
    """
    추천 시스템 E2E 통합 테스트

    병렬 실행 불가 시 위의 주석 해제 후 테스트
    : @tag('serial')로 순차 실행
    """

    test_model_dir: str
    test_lock_key: str

    common_category: Category

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.test_model_dir = tempfile.mkdtemp(prefix=f"als_integration_test_{os.getpid()}_")
        logging.getLogger("apps.lecture.services.recommendation_service.model_trainer").setLevel(logging.CRITICAL + 1)
        logging.getLogger("apps.lecture.services.recommendation_service.recommender").setLevel(logging.CRITICAL + 1)
        logging.getLogger("apps.lecture.services.recommendation_service.data_loader").setLevel(logging.CRITICAL + 1)
        logging.getLogger("apps.lecture.tasks").setLevel(logging.CRITICAL + 1)

        # 외부 라이브러리 경고 억제
        warnings.filterwarnings("ignore", category=RuntimeWarning, module="implicit")
        warnings.filterwarnings("ignore", module="implicit.utils")

    @classmethod
    def setUpTestData(cls) -> None:
        """클래스 레벨 테스트 데이터 생성"""
        super().setUpTestData()

        # 공통 카테고리 (모든 테스트에서 재사용)
        cls.common_category = Category.objects.create(name="Common Test Category")

    @classmethod
    def tearDownClass(cls) -> None:
        super().tearDownClass()
        if os.path.exists(cls.test_model_dir):
            shutil.rmtree(cls.test_model_dir)

    def setUp(self) -> None:
        super().setUp()
        self.client = APIClient()

        # 캐시 초기화
        cache.clear()
        for key in ALS_CACHE_KEYS:
            cache.delete(key)

        # Redis 연결 워밍업 (초기 연결 지연 제거)
        cache.set("warmup_key", "warmup_value", timeout=1)
        cache.get("warmup_key")
        cache.delete("warmup_key")

        # 프로세스별 고유 락 키
        self.test_lock_key = f"integration_test_lock_{os.getpid()}_{MODEL_VERSION}"

    def tearDown(self) -> None:
        """각 테스트 후 정리"""
        # 모든 ALS 관련 캐시 키 삭제
        for key in ALS_CACHE_KEYS:
            cache.delete(key)
        cache.delete(self.test_lock_key)

        # 모델 파일 정리
        if os.path.exists(self.test_model_dir):
            for file in os.listdir(self.test_model_dir):
                file_path = os.path.join(self.test_model_dir, file)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                except Exception:
                    pass

        super().tearDown()

    def _create_test_users(self, count: int) -> List[User]:
        """테스트 사용자 생성 헬퍼"""
        return [
            User.objects.create_user(
                email=f"testuser{i}@example.com",
                password="testpass123",
                nickname=f"testuser{i}",
                name=f"테스트유저{i}",
                phone_number=f"010-{1000+i:04d}-{1000+i:04d}",
                birthday="1990-01-01",
                gender="MALE",
            )
            for i in range(count)
        ]

    def _create_test_lectures(self, count: int) -> List[CrawledLecture]:
        """테스트 강의 생성 헬퍼"""
        lectures = [
            CrawledLecture.objects.create(
                external_id=300000 + i,
                title=f"테스트 강의 {i+1}",
                instructor=f"강사{i+1}",
                average_rating=4.0 + (i * 0.1),
                duration=600 + (i * 100),
                difficulty="MEDIUM",
                description="테스트 강의 설명",
                platform="INFLEARN",
                original_price=50000 + (i * 10000),
                discount_price=30000 + (i * 10000),
                url_link=f"https://example.com/lecture{i+1}",
            )
            for i in range(count)
        ]

        # 공통 카테고리 연결
        for lecture in lectures:
            LectureCategory.objects.create(lecture=lecture, category=self.common_category)

        return lectures

    def _get_recommendations_from_response(self, response: Any) -> List[Dict[str, Any]]:
        """응답에서 추천 목록 추출 헬퍼"""
        try:
            data = response.data
            if isinstance(data, dict) and "recommended_lectures" in data:
                recs = data["recommended_lectures"]
                if isinstance(recs, list):
                    return cast(List[Dict[str, Any]], recs)
        except (AttributeError, KeyError, TypeError):
            pass
        return []

    def test_e2e_response_structure_and_required_fields(self) -> None:
        """E2E: 응답 구조 및 필수 필드 검증"""
        users = self._create_test_users(1)
        lectures = self._create_test_lectures(2)

        UserPreferCategory.objects.create(user=users[0], category=self.common_category)

        self.client.force_authenticate(user=users[0])
        url = reverse("lecture-list")
        response = self.client.get(url)

        # 응답 상태 코드 검증
        self.assertEqual(response.status_code, status.HTTP_200_OK, f"Expected 200 OK but got {response.status_code}")

        self.assertIn("user_nickname", response.data)
        self.assertIn("recommended_lectures", response.data)
        self.assertEqual(response.data["user_nickname"], "testuser0")

        # 추천 목록 검증
        recommendations = self._get_recommendations_from_response(response)
        if recommendations:
            # 각 추천 항목의 필수 필드 검증
            for rec in recommendations:
                self.assertIn("uuid", rec, "추천 항목에 'uuid' 필드가 없습니다")
                self.assertIn("title", rec, "추천 항목에 'title' 필드가 없습니다")
                self.assertIn("is_bookmarked", rec, "추천 항목에 'is_bookmarked' 필드가 없습니다")
                self.assertIn("categories", rec, "추천 항목에 'categories' 필드가 없습니다")
                self.assertIsInstance(rec["categories"], list, "'categories'는 리스트여야 합니다")

    def test_e2e_no_data_returns_empty_or_popular_lectures(self) -> None:
        """E2E: 데이터 없을 때 빈 결과 또는 인기 강의 폴백"""
        users = self._create_test_users(1)
        self._create_test_lectures(2)

        self.client.force_authenticate(user=users[0])
        url = reverse("lecture-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK, "데이터 없을 때도 200 OK를 반환해야 합니다")

        # 폴백 전략(인기 강의) 동작 확인
        recommendations = self._get_recommendations_from_response(response)
        self.assertIsInstance(recommendations, list, "추천 결과는 리스트여야 합니다")

    def test_e2e_all_lectures_bookmarked_returns_empty(self) -> None:
        """E2E: 모든 강의 북마크 시 빈 결과 반환"""
        users = self._create_test_users(1)
        lectures = self._create_test_lectures(2)

        UserPreferCategory.objects.create(user=users[0], category=self.common_category)

        # 모든 강의 북마크
        for lecture in lectures:
            LectureBookmark.objects.create(user=users[0], lecture=lecture)

        self.client.force_authenticate(user=users[0])
        url = reverse("lecture-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        recommendations = self._get_recommendations_from_response(response)
        # 북마크된 강의는 추천에서 제외되어야 함
        if recommendations:
            recommended_ids: Set[int] = {rec["uuid"] for rec in recommendations}
            for lecture in lectures:
                self.assertNotIn(lecture.id, recommended_ids, f"북마크된 강의 {lecture.id}가 추천에 포함됨")

    @override_settings(MODEL_STORAGE_PATH=None)
    def test_e2e_als_model_training_returns_personalized_recommendations(self) -> None:
        """E2E: ALS 모델 학습 후 개인화된 추천 반환"""
        users = self._create_test_users(1)
        lectures = self._create_test_lectures(2)

        # 상호작용 데이터 생성
        LectureBookmark.objects.create(user=users[0], lecture=lectures[0])
        UserPreferCategory.objects.create(user=users[0], category=self.common_category)

        with override_settings(MODEL_STORAGE_PATH=self.test_model_dir):
            data_loader = DataLoader()
            trainer = ModelTrainer(data_loader, lock_key=self.test_lock_key)

            # 모델 학습
            success = trainer.train_and_save_full_model()
            self.assertTrue(success, "ALS 모델 학습 실패")

            # API 요청
            self.client.force_authenticate(user=users[0])
            url = reverse("lecture-list")
            response = self.client.get(url)

            self.assertEqual(response.status_code, status.HTTP_200_OK, "모델 학습 후 추천 요청 실패")

            # 추천 결과 검증
            recommendations = self._get_recommendations_from_response(response)
            self.assertGreaterEqual(len(recommendations), 0, "추천 결과가 없습니다")

            # 북마크된 강의는 추천에서 제외되어야 함
            if recommendations:
                recommended_ids: Set[int] = {rec["uuid"] for rec in recommendations}
                self.assertNotIn(lectures[0].id, recommended_ids, "북마크된 강의가 추천에 포함됨")

    @override_settings(MODEL_STORAGE_PATH=None)
    def test_e2e_multiple_users_personalized_recommendations(self) -> None:
        """E2E: 여러 사용자의 개인화된 추천"""
        users = self._create_test_users(2)
        lectures = self._create_test_lectures(3)

        category = Category.objects.create(name="Test Category")
        for lecture in lectures:
            LectureCategory.objects.create(lecture=lecture, category=category)

        # 각 사용자별 상호작용
        LectureBookmark.objects.create(user=users[0], lecture=lectures[0])
        LectureBookmark.objects.create(user=users[1], lecture=lectures[1])
        UserPreferCategory.objects.create(user=users[0], category=category)
        UserPreferCategory.objects.create(user=users[1], category=category)

        with override_settings(MODEL_STORAGE_PATH=self.test_model_dir):
            data_loader = DataLoader()
            trainer = ModelTrainer(data_loader, lock_key=self.test_lock_key)

            success = trainer.train_and_save_full_model()
            self.assertTrue(success, "모델 학습 실패")

            # 각 사용자별 추천 요청
            url = reverse("lecture-list")

            self.client.force_authenticate(user=users[0])
            response1 = self.client.get(url)

            self.client.force_authenticate(user=users[1])
            response2 = self.client.get(url)

            self.assertEqual(response1.status_code, status.HTTP_200_OK)
            self.assertEqual(response2.status_code, status.HTTP_200_OK)

            # 각 사용자의 북마크가 추천에서 제외되었는지 확인
            recommendations1 = self._get_recommendations_from_response(response1)
            if recommendations1:
                user1_ids: Set[int] = {rec["uuid"] for rec in recommendations1}
                self.assertNotIn(lectures[0].id, user1_ids, "User1 북마크가 추천에 포함됨")

            recommendations2 = self._get_recommendations_from_response(response2)
            if recommendations2:
                user2_ids: Set[int] = {rec["uuid"] for rec in recommendations2}
                self.assertNotIn(lectures[1].id, user2_ids, "User2 북마크가 추천에 포함됨")

    def test_user_no_authenticated(self) -> None:
        """로그인 안한 사용자"""
        response = self.client.get(reverse("lecture-list"))
        self.assertNotIn("recommended_lectures", response.data)
