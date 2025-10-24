import os
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models.query import QuerySet
from django.urls import reverse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase
from scipy.sparse import coo_matrix

from apps.lecture.models import (
    Category,
    CrawledLecture,
    CrawledLectureReview,
    LectureBookmark,
    LectureCategory,
    LectureSearchLog,
    UserPreferCategory,
)
from apps.lecture.services.constants import INTERACTION_WEIGHTS, RATING_SCORE_MAP
from apps.lecture.services.data_loader import DataLoader
from apps.lecture.services.model_trainer import ModelTrainer
from apps.lecture.services.recommender import RecommendationService

User = get_user_model()


class EmptyDataLoader(DataLoader):
    def build_user_item_matrix(self, target_user_ids: Optional[List[int]] = None) -> Tuple[
        Optional[coo_matrix],
        Optional[Dict[int, int]],
        Optional[Dict[int, int]],
        Optional[List[int]],
        Optional[List[int]],
    ]:
        return None, None, None, None, None


class RecommendationAPIViewIntegrationTest(APITestCase):
    def setUp(self) -> None:
        self.user = User.objects.create(
            email="test@example.com",
            nickname="testnick",
            name="테스트 이름",
            phone_number="01012345678",
            birthday="2000-01-01",
            gender="M",
            is_active=True,
            is_staff=False,
            is_superuser=False,
        )
        self.user.set_password("password123")
        self.user.save()
        self.client.force_authenticate(user=self.user)
        self.url = reverse("recommendations")

        self.categories = [Category.objects.create(name=f"카테고리 {i}") for i in range(3)]

        self.lectures: List[CrawledLecture] = []
        for i in range(5):
            lec = CrawledLecture.objects.create(
                uuid=str(uuid.uuid4()),
                title=f"테스트 강의 {i}",
                instructor=f"강사 {i}",
                thumbnail_img_url=f"https://mock.com/thumb{i}.jpg",
                difficulty="NORMAL",
                original_price=100000,
                discount_price=80000,
                platform="INFLEARN",
                average_rating=4.5,
                duration=120,
                url_link=f"https://mock.com/course/{i}",
                description="테스트용 설명",
            )
            LectureCategory.objects.create(lecture=lec, category=self.categories[i % 3])
            self.lectures.append(lec)

        LectureBookmark.objects.create(user=self.user, lecture=self.lectures[0])
        LectureSearchLog.objects.create(user=self.user, keyword="테스트")
        UserPreferCategory.objects.create(user=self.user, category=self.categories[0])
        CrawledLectureReview.objects.create(lecture=self.lectures[0], rating="5_OUT_OF_5_STARS")

        self.model_dir = getattr(settings, "MODEL_STORAGE_PATH", "/tmp/model_storage")
        os.makedirs(self.model_dir, exist_ok=True)
        for filename in ("als_model.npz", "als_mappings.npz"):
            path = os.path.join(self.model_dir, filename)
            if os.path.exists(path):
                os.remove(path)

    def test_train_model_no_interactions_returns_false(self) -> None:
        trainer = ModelTrainer(data_loader=EmptyDataLoader(weights=INTERACTION_WEIGHTS, rating_map=RATING_SCORE_MAP))
        result = trainer.train_and_save_full_model()
        self.assertFalse(result)

    def test_load_model_and_mappings_success(self) -> None:
        data_loader = DataLoader(weights=INTERACTION_WEIGHTS, rating_map=RATING_SCORE_MAP)
        trainer = ModelTrainer(data_loader=data_loader)
        trained = trainer.train_and_save_full_model()
        self.assertTrue(trained)

        model, u_to_i, l_to_i, users, lectures = trainer.load_model_and_mappings()
        self.assertIsNotNone(model)
        self.assertIsInstance(u_to_i, dict)
        self.assertIsInstance(l_to_i, dict)
        self.assertIsInstance(users, list)
        self.assertIsInstance(lectures, list)

    def test_model_caching_and_recommendations(self) -> None:
        service = RecommendationService()

        recommended_first = service.recommend_lectures_for_user(self.user.id, top_n=3)
        self.assertIsNotNone(recommended_first)

        recommended_second = service.recommend_lectures_for_user(self.user.id, top_n=3)
        self.assertIsNotNone(recommended_second)

    def test_als_pipeline_training_and_recommendation(self) -> None:
        data_loader = DataLoader(weights=INTERACTION_WEIGHTS, rating_map=RATING_SCORE_MAP)
        matrix, u_to_i, l_to_i, users, lectures = data_loader.build_user_item_matrix()
        self.assertIsNotNone(matrix)

        trainer = ModelTrainer(data_loader=data_loader)
        result = trainer.train_and_save_full_model()
        self.assertTrue(result)

        recommender = RecommendationService()
        recommended: Union[QuerySet[CrawledLecture], None] = recommender.recommend_lectures_for_user(
            self.user.id, top_n=3
        )
        self.assertIsNotNone(recommended)

        if recommended:
            rec_list = list(recommended)
            self.assertGreaterEqual(len(rec_list), 1)
            for lec in rec_list:
                self.assertIsInstance(lec.title, str)

    def test_recommendations_api_returns_expected_data(self) -> None:
        response: Response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("detail", response.data)
        self.assertIn("data", response.data)
        self.assertIn("recommendations", response.data["data"])

        recs: Union[List[Dict[str, Any]], None] = response.data["data"]["recommendations"]
        self.assertIsInstance(recs, list)
        self.assertGreaterEqual(len(recs), 1)

        expected_keys = {
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
        }
        self.assertTrue(expected_keys.issubset(recs[0].keys()))

    def test_recommendations_api_requires_authentication(self) -> None:
        self.client.logout()
        response: Response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
