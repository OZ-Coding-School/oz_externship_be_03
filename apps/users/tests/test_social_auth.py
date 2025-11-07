from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch
from django.conf import settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.core.exceptions import ValidationError
from requests import RequestException


from apps.users.models import User
from apps.users.services.social_auth_services import SocialAuthService


# ✅ 목모드 강제 활성화
settings.DEBUG = True


# ======================================================
# ✅ 정상 플로우 테스트
# ======================================================
class TestSocialAuthFlow(APITestCase):
    """소셜 로그인 플로우 통합 테스트 (카카오/네이버, MOCK 모드)"""

    def setUp(self) -> None:
        """테스트용 유저 초기화"""
        self.base_user_data = {
            "email": "mock_social_user@example.com",
            "name": "모크유저",
            "nickname": "mockie",
            "gender": "male",
            "birthday": "1995-05-05",
            "phone_number": "01012345678",
        }

    @patch("apps.users.services.social_auth_services.requests.post")
    @patch("apps.users.services.social_auth_services.requests.get")
    def test_kakao_social_login_flow(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """✅ 카카오 로그인 - 전체 서비스 로직 + 목데이터"""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"access_token": "mock_access_token_for_kakao"}

        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "id": "9999",
            "kakao_account": {
                "email": self.base_user_data["email"],
                "profile": {
                    "nickname": self.base_user_data["nickname"],
                    "profile_image_url": "https://mock.image/kakao.png",
                },
                "gender": "male",
                "birthdate": "1995-05-05",
                "phone_number": "+82 10-1234-5678",
            },
        }

        kakao_url = reverse("users:social-login", kwargs={"provider": "kakao"})
        response = self.client.post(kakao_url, {"code": "FAKE_KAKAO_CODE"}, format="json")

        print("\n🔹 [KAKAO LOGIN RESPONSE]")
        print("status:", response.status_code)
        print("data:", getattr(response, "data", {}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("카카오 로그인", response.data["detail"])

    @patch("apps.users.services.social_auth_services.requests.post")
    @patch("apps.users.services.social_auth_services.requests.get")
    def test_naver_social_login_flow(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """✅ 네이버 로그인 - 전체 서비스 로직 + 목데이터"""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"access_token": "mock_access_token_for_naver"}

        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "response": {
                "id": "8888",
                "email": self.base_user_data["email"],
                "name": self.base_user_data["name"],
                "nickname": self.base_user_data["nickname"],
                "gender": "F",
                "birthyear": "1996",
                "birthday": "05-05",
                "mobile": "+82 10-9876-5432",
                "profile_image": "https://mock.image/naver.png",
            }
        }

        naver_url = reverse("users:social-login", kwargs={"provider": "naver"})
        response = self.client.post(
            naver_url,
            {"code": "FAKE_NAVER_CODE", "state": "RANDOM_STATE"},
            format="json",
        )

        print("\n🔹 [NAVER LOGIN RESPONSE]")
        print("status:", response.status_code)
        print("data:", getattr(response, "data", {}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("네이버 로그인", response.data["detail"])


# ======================================================
# ✅ 예외 플로우 테스트 (커버리지 향상)
# ======================================================
class TestSocialAuthErrorCases(APITestCase):
    """소셜 로그인 서비스 예외 흐름 테스트"""

    def test_exchange_code_for_token_invalid_code(self) -> None:
        """❌ 잘못된 인가 코드로 토큰 요청 실패"""
        from apps.users.services.social_auth_services import KakaoAuthService
        with self.assertRaises(ValidationError):
            KakaoAuthService.exchange_code_for_token("INVALID_CODE")

    def test_handle_social_login_invalid_provider(self) -> None:
        """❌ 지원하지 않는 provider 전달 시 ValidationError"""
        from apps.users.services.social_auth_services import SocialAuthService
        with self.assertRaises(ValidationError):
            SocialAuthService.handle_social_login("twitter", "FAKE_CODE")
