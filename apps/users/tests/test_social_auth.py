from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.models import User


class TestSocialAuthFlow(APITestCase):
    """카카오 소셜 로그인 → 내정보조회 → 로그아웃 플로우 통합 테스트"""

    user: User

    def setUp(self) -> None:
        """테스트용 유저 생성"""
        self.user = User.objects.create_user(
            email="socialflow@example.com",
            name="소셜유저",
            nickname="socialflow",
            birthday="1990-01-01",
            gender="male",
            phone_number="01012345678",
        )
        self.user.is_active = True
        self.user.save()

    @patch("apps.users.services.social_auth_services.SocialAuthService.handle_social_login")
    def test_social_login_me_logout_flow(self, mock_social_login: MagicMock) -> None:
        """카카오 소셜 로그인 → 내정보조회 → 로그아웃 플로우 테스트"""

        # ✅ 실제 JWT 토큰 발급 (mock이지만 유효한 토큰)
        refresh = RefreshToken.for_user(self.user)
        access = str(refresh.access_token)

        mock_social_login.return_value = {
            "detail": "Kakao 로그인에 성공했습니다.",
            "access": access,
            "refresh": str(refresh),
        }

        # ✅ 1️⃣ 로그인 요청
        kakao_url = reverse("users:kakao-login")
        response = self.client.post(kakao_url, {"code": "mock_code"}, format="json")
        print("🔹 LOGIN response:", response.status_code, getattr(response, "data", {}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("로그인", response.data["detail"])

        # ✅ 2️⃣ access 토큰 헤더 설정
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        print("🟢 AUTH HEADER SET:", getattr(self.client, "_credentials", None))

        # ✅ refresh 쿠키 저장
        self.client.cookies[settings.AUTH_REFRESH_COOKIE_NAME] = str(refresh)
        print("🟡 REFRESH COOKIE:", self.client.cookies.get(settings.AUTH_REFRESH_COOKIE_NAME))

        # ✅ 3️⃣ 내정보 조회
        me_url = reverse("users:me")
        response = self.client.get(me_url)
        print("🔸 ME response:", response.status_code, getattr(response, "data", {}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], self.user.email)

        # ✅ 4️⃣ 로그아웃 요청
        logout_url = reverse("users:auth_logout")
        response = self.client.post(logout_url)
        print("🔻 LOGOUT response:", response.status_code, getattr(response, "data", {}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("로그아웃", response.data["detail"])

        # ✅ 5️⃣ 로그아웃 후 내정보 조회
        response = self.client.get(me_url)
        print("🔴 AFTER LOGOUT me:", response.status_code, getattr(response, "data", {}))

        # 최소 로그아웃 정책 → access는 남아 있을 수 있음
        self.assertIn(response.status_code, [200, 401])
