from typing import Any
from unittest.mock import MagicMock, patch

from django.urls import reverse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from apps.users.models import User

class TestSocialAuthView(APITestCase):
    """카카오 / 네이버 소셜 로그인 API 통합 테스트"""

    @patch("apps.users.services.social_auth_services.requests.get")
    @patch("apps.users.services.social_auth_services.requests.post")
    def test_kakao_login_request_returns_access_token(self, mock_post: MagicMock, mock_get: MagicMock) -> None:
        """카카오 로그인 요청 → 인가코드로 access_token 받아오기"""

        # 1️⃣ Mock access_token 응답
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"access_token": "dummy_kakao_token"}

        # 2️⃣ Mock 사용자 정보 응답
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "id": "12345",
            "kakao_account": {
                "email": "test@example.com",
                "name": "홍길동",
                "gender": "male",  # ✅ 성별 추가
                "phone_number": "01012345678",
                "birthday": "2020-01-01",
                "profile": {
                    "nickname": "테스트유저",
                    "profile_image_url": "https://test.image.url/profile.png",
                },
            },
        }

        # 3️⃣ 요청
        url: str = reverse("users:kakao-login")
        data: dict[str, Any] = {"code": "dummy_auth_code"}

        response: Response = self.client.post(url, data, format="json")

        # ✅ 디버깅 출력
        print("\n[DEBUG - Kakao]")
        print("URL:", url)
        print("Request Data:", data)
        print("Status Code:", response.status_code)
        print("Response Data:", response.data)
        print("Mock post called:", mock_post.called)
        print("Mock get called:", mock_get.called)

        # ✅ 검증
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("detail", response.data)
        self.assertEqual(response.data["detail"], "Kakao 로그인에 성공했습니다.")

    # -----------------------------------------------------------------------

    @patch("apps.users.services.social_auth_services.requests.get")
    @patch("apps.users.services.social_auth_services.requests.post")
    def test_naver_login_request_returns_access_token(self, mock_post: MagicMock, mock_get: MagicMock) -> None:
        """네이버 로그인 요청 → 인가코드로 access_token 받아오기"""

        # 1️⃣ Mock access_token 응답
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"access_token": "dummy_naver_token"}

        # 2️⃣ Mock 사용자 정보 응답
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "response": {
                "id": "99999",
                "email": "naver@test.com",
                "nickname": "네이버유저",
                "name": "홍길동",
                "gender": "F",  # ✅ 성별 추가
                "mobile": "01099998888",
                "birthday": "2020-02-02",
                "profile_image": "https://test.image.url/naver.png",
            }
        }

        # 3️⃣ 요청
        url: str = reverse("users:naver-login")
        data: dict[str, Any] = {"code": "dummy_auth_code", "state": "xyz"}

        response: Response = self.client.post(url, data, format="json")

        # ✅ 디버깅 출력
        print("\n[DEBUG - Naver]")
        print("URL:", url)
        print("Request Data:", data)
        print("Status Code:", response.status_code)
        print("Response Data:", response.data)
        print("Mock post called:", mock_post.called)
        print("Mock get called:", mock_get.called)

        # ✅ 검증
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("detail", response.data)
        self.assertEqual(response.data["detail"], "Naver 로그인에 성공했습니다.")

    # -----------------------------------------------------------------------

    @patch("apps.users.services.social_auth_services.requests.get")
    @patch("apps.users.services.social_auth_services.requests.post")
    def test_invalid_provider_returns_400(self, mock_post: MagicMock, mock_get: MagicMock) -> None:
        """지원하지 않는 provider면 400"""

        url: str = "/api/v1/auth/social/google/"
        data: dict[str, Any] = {"code": "dummy_code"}

        response: Response = self.client.post(url, data, format="json")

        # ✅ 디버깅 출력
        print("\n[DEBUG - Invalid Provider]")
        print("URL:", url)
        print("Status Code:", response.status_code)
        print("Response Data:", response.data)

        # ✅ 검증
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("지원하지 않는 provider", response.data["detail"])

@patch("apps.users.services.social_auth_services.requests.get")
@patch("apps.users.services.social_auth_services.requests.post")
def test_kakao_login_existing_user_success(self, mock_post, mock_get):
    """기존 카카오 유저 로그인 성공"""
    # given
    User.objects.create_user(
        email="test@example.com",
        password="1234",
        name="홍길동",
        nickname="테스트유저"
    )
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"access_token": "dummy_token"}
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        "id": "12345",
        "kakao_account": {"email": "test@example.com", "profile": {"nickname": "테스트유저"}}
    }

    # when
    response = self.client.post(reverse("users:kakao-login"), {"code": "dummy_code"}, format="json")

    # then
    self.assertEqual(response.status_code, status.HTTP_200_OK)
    self.assertEqual(response.data["detail"], "Kakao 로그인에 성공했습니다.")

@patch("apps.users.services.social_auth_services.requests.get")
@patch("apps.users.services.social_auth_services.requests.post")
def test_kakao_login_existing_user_success(self, mock_post, mock_get):
    """기존 카카오 유저 로그인 성공"""
    # given
    User.objects.create_user(
        email="test@example.com",
        password="1234",
        name="홍길동",
        nickname="테스트유저"
    )
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"access_token": "dummy_token"}
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        "id": "12345",
        "kakao_account": {"email": "test@example.com", "profile": {"nickname": "테스트유저"}}
    }

    # when
    response = self.client.post(reverse("users:kakao-login"), {"code": "dummy_code"}, format="json")

    # then
    self.assertEqual(response.status_code, status.HTTP_200_OK)
    self.assertEqual(response.data["detail"], "Kakao 로그인에 성공했습니다.")
