from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class CategoryListAPITest(APITestCase):
    def setUp(self) -> None:
        self.category_list_url = reverse("category-list")

    def test_category_list_mock_data(self) -> None:
        response = self.client.get(self.category_list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("id", response.json()[0])
        self.assertIn("name", response.json()[2])
