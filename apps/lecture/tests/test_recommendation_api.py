from datetime import date
from typing import Any, ClassVar
from unittest import mock

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class RecommendationApiViewTest(APITestCase):
    _user: ClassVar[Any]
    _recommendations_url: ClassVar[str]

    @classmethod
    def setUpTestData(cls) -> None:
        """테스트 데이터 설정: 클래스당 한 번만 실행"""
        cls._user = User.objects.create_user(
            email="testuser@example.com",
            nickname="testnick",
            name="테스트 이름",
            phone_number="01012345678",
            birthday=date(2000, 1, 1),
            gender="M",
            is_active=True,
            is_staff=False,
            is_superuser=False,
            password="securepassword123",
        )
        cls._recommendations_url = reverse("recommendations")

    def setUp(self) -> None:
        """각 테스트 케이스 시작 전 실행"""
        self.user = self.__class__._user
        self.recommendations_url = self.__class__._recommendations_url

    def test_requires_authentication(self) -> None:
        """인증되지 않은 사용자는 401 Unauthorized 응답을 받아야 함"""
        response: Any = self.client.get(self.recommendations_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("detail", response.data)

    def test_user_id_is_missing_returns_401(self) -> None:
        """
        request.user.id가 None일 때 401 응답을 반환하는지 확인
        RecommendationView의 get_recommendation_service 경로를 Mocking.
        """
        self.client.force_authenticate(user=self.user)

        # request.user.id가 None이 되도록 mocking.
        with mock.patch("rest_framework.request.Request.user", new_callable=mock.PropertyMock) as mock_user_prop:
            # mock user 객체가 id 속성을 None으로 반환하도록 설정
            mock_user_prop.return_value = mock.Mock(id=None)

            response: Any = self.client.get(self.recommendations_url)

            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
            self.assertEqual(response.data.get("detail"), "User ID is missing.")

    def test_authenticated_user_gets_recommendations(self) -> None:
        """인증된 사용자는 200 OK 응답을 받고 리스트 형태의 추천 데이터를 받아야 함"""
        self.client.force_authenticate(user=self.user)
        response: Any = self.client.get(self.recommendations_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertIsInstance(response.data, list)
        self.assertLessEqual(len(response.data), 3)  # 추천 개수 상한선 확인

    def test_response_structure(self) -> None:
        """추천 응답 데이터가 필수 필드를 포함하는지 확인"""
        self.client.force_authenticate(user=self.user)
        response: Any = self.client.get(self.recommendations_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        if response.data:
            first_lecture = response.data[0]
            required_fields = [
                "id",
                "uuid",
                "title",
                "instructor",
                "thumbnail_img_url",
                "difficulty",
                "original_price",
                "discount_price",
                "platform",
                "average_rating",
                "url_link",
                "is_bookmarked",
                "categories",
            ]
            for field in required_fields:
                self.assertIn(field, first_lecture)
