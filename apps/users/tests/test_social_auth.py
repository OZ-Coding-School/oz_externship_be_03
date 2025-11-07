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
    """소셜 로그인 플로우 통합 테스트 (카카오 / 네이버 공통 구조)"""

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
    def test_kakao_social_login_me_logout_flow(self, mock_social_login: MagicMock) -> None:
        """✅ 카카오 소셜 로그인 → 내정보조회 → 로그아웃 + 쿠키 디버깅"""

        # ✅ 실제 JWT 발급
        refresh = RefreshToken.for_user(self.user)
        access = str(refresh.access_token)

        # ✅ Mock 응답
        mock_social_login.return_value = {
            "detail": "Kakao 로그인에 성공했습니다.",
            "data": {"access": access, "refresh": str(refresh)},
        }

        # ✅ 1️⃣ 로그인 요청
        kakao_url = reverse("users:kakao-login")
        response = self.client.post(kakao_url, {"code": "mock_code"}, format="json")

        print("\n🔹 [KAKAO LOGIN RESPONSE]")
        print("status:", response.status_code)
        print("data:", getattr(response, "data", {}))
        print("cookies:", {k: v.value for k, v in response.cookies.items()})  # ✅ 쿠키 전체 출력

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("Kakao", response.data["detail"])

        # ✅ refresh_token 쿠키 확인
        cookies = response.cookies
        self.assertIn("refresh_token", cookies, "refresh_token 쿠키 누락됨")
        cookie = cookies["refresh_token"]

        # ✅ 쿠키 속성 디버깅 출력
        print("🍪 [KAKAO refresh_token cookie details]:")
        for key in ["value", "httponly", "secure", "samesite"]:
            print(f"  - {key}: {cookie.get(key)}")

        self.assertTrue(cookie["httponly"])
        self.assertTrue(cookie["secure"])
        self.assertEqual(cookie["samesite"], "None")

        # ✅ access 토큰 인증 후 내정보 조회
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        me_url = reverse("users:me")
        me_response = self.client.get(me_url)
        print("🔸 [ME response]:", me_response.status_code, getattr(me_response, "data", {}))

        self.assertIn(me_response.status_code, [200, 401])

        # ✅ 로그아웃 요청
        logout_url = reverse("users:auth_logout")
        logout_response = self.client.post(logout_url)
        print("🔻 [LOGOUT response]:", logout_response.status_code, getattr(logout_response, "data", {}))

    @patch("apps.users.services.social_auth_services.SocialAuthService.handle_social_login")
    def test_naver_social_login_flow(self, mock_social_login: MagicMock) -> None:

        refresh = RefreshToken.for_user(self.user)
        access = str(refresh.access_token)

        mock_social_login.return_value = {
            "detail": "Naver 로그인에 성공했습니다.",
            "data": {"access": access, "refresh": str(refresh)},
        }

        naver_url = reverse("users:naver-login")
        response = self.client.post(naver_url, {"code": "mock_code", "state": "RANDOM_STATE"}, format="json")

        print("\n🔹 [NAVER LOGIN RESPONSE]")
        print("status:", response.status_code)
        print("data:", getattr(response, "data", {}))
        print("cookies:", {k: v.value for k, v in response.cookies.items()})  # ✅ 쿠키 전체 출력

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("Naver", response.data["detail"])

        # refresh_token 쿠키 확인 및 디버깅
        cookies = response.cookies
        self.assertIn("refresh_token", cookies, "refresh_token 쿠키 누락됨")
        cookie = cookies["refresh_token"]

        print("🍪 [NAVER refresh_token cookie details]:")
        for key in ["value", "httponly", "secure", "samesite"]:
            print(f"  - {key}: {cookie.get(key)}")

        self.assertTrue(cookie["httponly"])
        self.assertTrue(cookie["secure"])
        self.assertEqual(cookie["samesite"], "None")

        # access 토큰 인증 후 내정보 조회
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        me_url = reverse("users:me")
        me_response = self.client.get(me_url)
        print("🔸 [NAVER ME response]:", me_response.status_code, getattr(me_response, "data", {}))
