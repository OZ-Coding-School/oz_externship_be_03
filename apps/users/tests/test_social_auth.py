from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken  # ✅ 추가

from apps.users.models import User


class TestSocialAuthView(APITestCase):
    """소셜 로그인 전체 통합 테스트 (카카오 / 네이버 / 잘못된 provider / 내정보조회)"""

    @patch("apps.users.services.social_auth_services.requests.get")
    @patch("apps.users.services.social_auth_services.requests.post")
    def test_kakao_login_new_user_success(self, mock_post: MagicMock, mock_get: MagicMock) -> None:  # ✅ type hint 명확
        ...

    @patch("apps.users.services.social_auth_services.requests.get")
    @patch("apps.users.services.social_auth_services.requests.post")
    def test_kakao_login_existing_user_success(self, mock_post: MagicMock, mock_get: MagicMock) -> None:
        ...

    @patch("apps.users.services.social_auth_services.requests.get")
    @patch("apps.users.services.social_auth_services.requests.post")
    def test_kakao_login_then_me(self, mock_post: MagicMock, mock_get: MagicMock) -> None:
        ...

    @patch("apps.users.services.social_auth_services.requests.get")
    @patch("apps.users.services.social_auth_services.requests.post")
    def test_naver_login_request_returns_access_token(self, mock_post: MagicMock, mock_get: MagicMock) -> None:
        ...

    def test_invalid_provider_returns_400(self) -> None:
        ...

    @patch("apps.users.services.social_auth_services.requests.get")
    @patch("apps.users.services.social_auth_services.requests.post")
    def test_kakao_login_token_fail(self, mock_post: MagicMock, mock_get: MagicMock) -> None:
        ...

    @patch("apps.users.services.social_auth_services.requests.get")
    @patch("apps.users.services.social_auth_services.requests.post")
    def test_kakao_userinfo_fail(self, mock_post: MagicMock, mock_get: MagicMock) -> None:
        ...

    @patch("apps.users.services.social_auth_services.requests.get")
    @patch("apps.users.services.social_auth_services.requests.post")
    def test_naver_userinfo_fail(self, mock_post: MagicMock, mock_get: MagicMock) -> None:
        ...

    def test_meview_unauthenticated(self) -> None:
        ...

    def test_logout_success(self) -> None:  # ✅ type hint 명확히
        """유효한 refresh/access 쿠키가 있을 때 로그아웃 성공"""
        user = User.objects.create_user(
            email="logoutuser@example.com",
            password="1234",
            name="로그아웃유저",
            nickname="logoutuser",
            birthday="1990-01-01",
            gender="M",
            phone_number="01012345678",
        )
        self.client.force_authenticate(user=user)

        refresh: RefreshToken = RefreshToken.for_user(user)
        access: AccessToken = AccessToken.for_user(user)

        self.client.cookies[settings.AUTH_REFRESH_COOKIE_NAME] = str(refresh)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        response = self.client.post(reverse("users:auth_logout"), format="json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("detail", response.data)
        self.assertIn("로그아웃", response.data["detail"])
        self.assertIsNone(response.cookies.get(settings.AUTH_REFRESH_COOKIE_NAME))

    def test_logout_invalid_token(self) -> None:
        """refresh 쿠키가 잘못된 값일 때 401 응답"""
        user = User.objects.create_user(
            email="invalidlogout@example.com",
            password="1234",
            name="로그아웃유저",
            nickname="invalidlogout",
            birthday="1990-01-01",
            gender="M",
            phone_number="01011112222",
        )
        self.client.force_authenticate(user=user)
        self.client.cookies[settings.AUTH_REFRESH_COOKIE_NAME] = "invalid_token"
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid_access")

        response = self.client.post(reverse("users:auth_logout"), format="json")
        self.assertEqual(response.status_code, 401)
        self.assertIn("error", response.data)
        self.assertIn("유효하지 않은 토큰", response.data["error"])

    def test_logout_without_cookie(self) -> None:
        """refresh 쿠키 없이 요청 시 세션 만료 안내"""
        user = User.objects.create_user(
            email="nocookie@example.com",
            password="1234",
            name="노쿠키유저",
            nickname="nocookie",
            birthday="1990-01-01",
            gender="M",
            phone_number="01099997777",
        )
        self.client.force_authenticate(user=user)
        response = self.client.post(reverse("users:auth_logout"), format="json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("detail", response.data)
        self.assertIn("세션이 유효하지 않습니다", response.data["detail"])
