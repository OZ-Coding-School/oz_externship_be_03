from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class AdminLectureAPITestCase(APITestCase):
    def setUp(self) -> None:
        self.admin_lecture_list_url = reverse("admin_lecture:admin-lecture-list")

    def test_admin_lecture_list_returns_mock_data(self) -> None:
        response = self.client.get(self.admin_lecture_list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("count", response.json())
        self.assertIn("results", response.json())
        self.assertEqual(response.data["count"], 150)
        self.assertEqual(len(response.data["results"]), 10)

    def test_admin_lecture_list_response_structure(self) -> None:
        response = self.client.get(self.admin_lecture_list_url)

        first_lecture = response.data["results"][0]
        required_fields = [
            "id",
            "title",
            "instructor",
            "thumbnail_img_url",
            "platform",
            "url_link",
            "categories",
            "created_at",
            "updated_at",
        ]

        for field in required_fields:
            self.assertIn(field, first_lecture)


class AdminLectureDetailApiViewTest(APITestCase):
    def setUp(self) -> None:
        self.admin_lecture_detail_url = reverse("admin_lecture:admin-lecture-detail", kwargs={"lecture_id": 1})

    def test_admin_lecture_detail_returns_mock_data(self) -> None:
        response = self.client.get(self.admin_lecture_detail_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], 1)

    def test_admin_lecture_detail_response_structure(self) -> None:
        response = self.client.get(self.admin_lecture_detail_url)

        required_fields = [
            "id",
            "uuid",
            "title",
            "instructor",
            "thumbnail_img_url",
            "description",
            "difficulty",
            "duration",
            "original_price",
            "discount_price",
            "platform",
            "url_link",
            "categories",
            "created_at",
            "updated_at",
        ]

        for field in required_fields:
            self.assertIn(field, response.data)
