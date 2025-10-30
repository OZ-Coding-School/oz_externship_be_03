from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.lecture.models import Category


class CategoryListAPITest(APITestCase):
    category_list_url: str
    category1: Category
    category2: Category
    category3: Category
    category4: Category

    @classmethod
    def setUpTestData(cls) -> None:
        cls.category_list_url = reverse("category-list")

        cls.category1, cls.category2, cls.category3, cls.category4 = Category.objects.bulk_create(
            [
                Category(name="Python"),
                Category(name="C++"),
                Category(name="Django"),
                Category(name="Spring"),
            ]
        )

    def test_category_list_data(self) -> None:
        """카테고리 조회 및 데이터 검증"""
        response = self.client.get(self.category_list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 4)
        self.assertEqual(response.data[3]["name"], "Spring")
