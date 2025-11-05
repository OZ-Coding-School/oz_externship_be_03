from typing import Any
from unittest.mock import MagicMock, patch
from django.urls import reverse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase
from apps.users.models import User


class TestSocialAuthView(APITestCase):
    """소셜 로그인 전체 통합 테스트 (카카오 / 네이버 / 잘못된 provider / 내정보조회)"""

    # ----------------------------------------------------------------------
    # ✅ 신규 카카오 유저 로그인
    # ----------------------------------------------------------------------
    @patch("apps.users.services.social_auth_services.requests.get")
    @patch("apps.users.services.social_auth_services.requests.post")
    def test_kakao_login_new_user_success(self, mock_post: MagicMock, mock_get: MagicMock) -> None:
        """카카오 로그인 → 신규 회원가입 성공"""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"access_token": "dummy_kakao_token"}
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "id": "kakao_12345",
            "kakao_account": {
                "email": "newuser@example.com",
                "name": "홍길동",
                "gender": "male",
                "phone_number": "01012345678",
                "birthday": "2000-01-01",
                "profile": {
                    "nickname": "신규유저",
                    "profile_image_url": "https://test.image.url/profile.png",
                },
            },
        }
        url = reverse("users:kakao-login")
        response = self.client.post(url, {"code": "dummy_auth_code"}, format="json")

        self.assertEqual(response.status_code, 200)
        user = User.objects.get(email="newuser@example.com")
        self.assertEqual(user.nickname, "신규유저")
        self.assertEqual(user.profile_img_url, "https://test.image.url/profile.png")
        self.assertEqual(user.gender, "M")

    # ----------------------------------------------------------------------
    # ✅ 기존 카카오 유저 로그인
    # ----------------------------------------------------------------------
    @patch("apps.users.services.social_auth_services.requests.get")
    @patch("apps.users.services.social_auth_services.requests.post")
    def test_kakao_login_existing_user_success(self, mock_post: MagicMock, mock_get: MagicMock) -> None:
        User.objects.create_user(
            email="test@example.com",
            password="1234",
            name="홍길동",
            nickname="테스트유저",
            birthday="1990-01-01",
            gender="male",
            phone_number="01099997777",
            profile_img_url="https://old.img/profile.png",
        )
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"access_token": "dummy_token"}
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "id": "12345",
            "kakao_account": {"email": "test@example.com", "profile": {"nickname": "테스트유저"}},
        }

        response = self.client.post(reverse("users:kakao-login"), {"code": "dummy_code"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), 1)

    # ----------------------------------------------------------------------
    # ✅ 신규 로그인 후 /me 조회
    # ----------------------------------------------------------------------
    @patch("apps.users.services.social_auth_services.requests.get")
    @patch("apps.users.services.social_auth_services.requests.post")
    def test_kakao_login_then_me(self, mock_post: MagicMock, mock_get: MagicMock) -> None:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"access_token": "dummy_kakao_token"}
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "id": "kakao_67890",
            "kakao_account": {
                "email": "meuser@example.com",
                "name": "홍길동",
                "gender": "male",
                "birthday": "1990-05-05",
                "phone_number": "01011112222",
                "profile": {
                    "nickname": "나의유저",
                    "profile_image_url": "https://test.image.url/profile_me.png",
                },
            },
        }

        response = self.client.post(reverse("users:kakao-login"), {"code": "dummy_auth_code"}, format="json")
        user = User.objects.get(email="meuser@example.com")
        self.client.force_authenticate(user=user)
        response_me = self.client.get(reverse("users:me"))
        self.assertEqual(response_me.status_code, 200)
        self.assertEqual(response_me.data["email"], "meuser@example.com")

    # ----------------------------------------------------------------------
    # ✅ 네이버 로그인 성공
    # ----------------------------------------------------------------------
    @patch("apps.users.services.social_auth_services.requests.get")
    @patch("apps.users.services.social_auth_services.requests.post")
    def test_naver_login_request_returns_access_token(self, mock_post: MagicMock, mock_get: MagicMock) -> None:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"access_token": "dummy_naver_token"}
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "response": {
                "id": "99999",
                "email": "naver@test.com",
                "nickname": "네이버유저",
                "name": "홍길동",
                "gender": "F",
                "mobile": "01099998888",
                "birthday": "2020-02-02",
                "profile_image": "https://test.image.url/naver.png",
            }
        }
        response = self.client.post(reverse("users:naver-login"), {"code": "dummy_auth_code", "state": "xyz"}, format="json")
        self.assertEqual(response.status_code, 200)

    # ----------------------------------------------------------------------
    # ✅ 지원하지 않는 provider
    # ----------------------------------------------------------------------
    def test_invalid_provider_returns_400(self) -> None:
        response = self.client.post("/api/v1/auth/social/google/", {"code": "dummy_code"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("지원하지 않는 provider", response.data["detail"])

    # ----------------------------------------------------------------------
    # ❌ 카카오 로그인 실패 - access_token 발급 실패
    # ----------------------------------------------------------------------
    @patch("apps.users.services.social_auth_services.requests.get")
    @patch("apps.users.services.social_auth_services.requests.post")
    def test_kakao_login_token_fail(self, mock_post: MagicMock, mock_get: MagicMock) -> None:
        mock_post.return_value.status_code = 400
        mock_post.return_value.json.return_value = {"error": "invalid_grant"}
        response = self.client.post(reverse("users:kakao-login"), {"code": "wrong_auth_code"}, format="json")
        self.assertEqual(response.status_code, 400)

    # ----------------------------------------------------------------------
    # ❌ 카카오 로그인 실패 - 사용자 정보 요청 실패
    # ----------------------------------------------------------------------
    @patch("apps.users.services.social_auth_services.requests.get")
    @patch("apps.users.services.social_auth_services.requests.post")
    def test_kakao_userinfo_fail(self, mock_post: MagicMock, mock_get: MagicMock) -> None:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"access_token": "dummy_token"}
        mock_get.return_value.status_code = 500
        mock_get.return_value.json.return_value = {"error": "server_error"}
        response = self.client.post(reverse("users:kakao-login"), {"code": "dummy_code"}, format="json")
        self.assertEqual(response.status_code, 400)

    # ----------------------------------------------------------------------
    # ❌ 네이버 로그인 실패 - userinfo 오류
    # ----------------------------------------------------------------------
    @patch("apps.users.services.social_auth_services.requests.get")
    @patch("apps.users.services.social_auth_services.requests.post")
    def test_naver_userinfo_fail(self, mock_post: MagicMock, mock_get: MagicMock) -> None:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"access_token": "dummy_token"}
        mock_get.return_value.status_code = 404
        mock_get.return_value.json.return_value = {"error": "not_found"}
        response = self.client.post(reverse("users:naver-login"), {"code": "dummy_code", "state": "xyz"}, format="json")
        self.assertEqual(response.status_code, 400)

    # ----------------------------------------------------------------------
    # ❌ MeView - 인증되지 않은 사용자
    # ----------------------------------------------------------------------
    def test_meview_unauthenticated(self) -> None:
        response = self.client.get(reverse("users:me"))
        self.assertEqual(response.status_code, 401)
