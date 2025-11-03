from typing import Any
from unittest.mock import MagicMock, patch

from django.urls import reverse
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.test import APITestCase


class TestSocialAuthView(APITestCase):
    """카카오 / 네이버 소셜 로그인 API 테스트"""

    @patch("apps.users.services.social_auth_services.SocialAuthService.social_login")
    @patch("apps.users.services.social_auth_services.requests.get")
    @patch("apps.users.views.social_auth_views.requests.post")
    def test_kakao_login_request_returns_access_token(self, mock_post: MagicMock, mock_get: MagicMock) -> None:
        """카카오 로그인 요청 → 인가코드로 access_token 받아오기"""
        # access_token 요청 mock
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"access_token": "dummy_kakao_token"}

        # 사용자 정보 요청 mock
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "id": "12345",
            "kakao_account": {
                "email": "test@example.com",
                "profile": {"nickname": "테스트유저"},
            },
        }

        url: str = reverse("users:kakao-login")
        data: dict[str, Any] = {"code": "dummy_auth_code"}

        response: Response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_post.assert_called_once_with(
            "https://kauth.kakao.com/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": "6d294023adf65d77ebc3332bd289cab6",
                "redirect_uri": "https://account.ozcoding.site/oauth/kakao",
                "code": "dummy_auth_code",
            },
        )

    @patch("apps.users.services.social_auth_services.requests.get")
    @patch("apps.users.views.social_auth_views.requests.post")
    def test_naver_login_request_returns_access_token(self, mock_post: MagicMock, mock_get: MagicMock) -> None:
        """네이버 로그인 요청 → 인가코드로 access_token 받아오기"""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"access_token": "dummy_naver_token"}

        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "response": {"id": "99999", "email": "naver@test.com", "nickname": "네이버유저"}
        }

        url: str = reverse("users:naver-login")
        data: dict[str, Any] = {"code": "dummy_auth_code", "state": "xyz"}

        response: Response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_post.assert_called_once_with(
            "https://nid.naver.com/oauth2.0/token",
            data={
                "grant_type": "authorization_code",
                "client_id": "djTn15iiZcKt3i6EJaHv",
                "client_secret": "xnHoLv5PYQ",
                "code": "dummy_auth_code",
                "state": "xyz",
            },
        )

    @patch("apps.users.services.social_auth_services.requests.get")
    @patch("apps.users.views.social_auth_views.requests.post")
    def test_invalid_provider_returns_400(self, mock_post: MagicMock, mock_get: MagicMock) -> None:
        """지원하지 않는 provider면 400"""
        url: str = "/api/v1/auth/social/google/"
        data: dict[str, Any] = {"code": "dummy_code"}

        response: Response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("지원하지 않는 provider입니다.", response.data["detail"])
