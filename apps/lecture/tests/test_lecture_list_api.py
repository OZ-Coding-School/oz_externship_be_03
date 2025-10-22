from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class LectureListApiViewTest(APITestCase):
    def setUp(self) -> None:
        self.lecture_list_url = reverse("lecture-list")

    def test_lecture_list_returns_mock_data(self) -> None:
        response = self.client.get(self.lecture_list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("count", response.json())
        self.assertIn("results", response.json())
        self.assertEqual(response.data["count"], 150)
        self.assertEqual(len(response.data["results"]), 10)

    def test_lecture_list_response_structure(self) -> None:
        response = self.client.get(self.lecture_list_url)

        first_lecture = response.data["results"][0]
        required_fields = ["id", "uuid", "title", "instructor", "categories", "platform", "is_bookmarked"]

        for field in required_fields:
            self.assertIn(field, first_lecture)


class LectureReviewListApiViewTest(APITestCase):
    def setUp(self) -> None:
        self.lecture_uuid = "550e8400-e29b-41d4-a716-446655440000"
        self.lecture_reviews_url = reverse("lecture-review-list", kwargs={"uuid": self.lecture_uuid})

    def test_lecture_review_list_returns_mock_data(self) -> None:
        response = self.client.get(self.lecture_reviews_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("reviews", response.data)
        self.assertEqual(len(response.data["reviews"]), 4)

    def test_lecture_review_list_response_structure(self) -> None:
        response = self.client.get(self.lecture_reviews_url)

        first_review = response.data["reviews"][0]
        required_fields = ["id", "rating", "content", "created_at"]

        for field in required_fields:
            self.assertIn(field, first_review)
