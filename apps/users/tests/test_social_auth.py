from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.users.models import User
from apps.users.services.social_auth_services import SocialAuthService


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

        # 1️⃣ access_token 발급 모킹
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"access_token": "mock_access_token_for_kakao"}

        # 2️⃣ 사용자 정보 응답 모킹
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
                "birthday": "0505",
                "birthyear": "1995",
                "phone_number": "+82 10-1234-5678",
            },
        }

        # ✅ 실제 코드 흐름 테스트 (FAKE 코드로 내부 로직 진입)
        kakao_url = reverse("users:social-login", kwargs={"provider": "kakao"})
        response = self.client.post(kakao_url, {"code": "FAKE_KAKAO_CODE"}, format="json")

        print("\n🔹 [KAKAO LOGIN RESPONSE]")
        print("status:", response.status_code)
        print("data:", getattr(response, "data", {}))
        print("cookies:", {k: v.value for k, v in response.cookies.items()})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("카카오 로그인", response.data["detail"])

        cookies = response.cookies
        self.assertIn("refresh_token", cookies)
        cookie = cookies["refresh_token"]
        self.assertTrue(cookie["httponly"])
        self.assertTrue(cookie["secure"])
        self.assertEqual(cookie["samesite"], "None")

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
                "birthday": "0505",
                "birthyear": "1996",
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
        print("cookies:", {k: v.value for k, v in response.cookies.items()})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("네이버 로그인", response.data["detail"])

        cookies = response.cookies
        self.assertIn("refresh_token", cookies)
        cookie = cookies["refresh_token"]
        self.assertTrue(cookie["httponly"])
        self.assertTrue(cookie["secure"])
        self.assertEqual(cookie["samesite"], "None")
