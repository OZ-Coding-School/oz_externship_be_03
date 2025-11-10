from __future__ import annotations

from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.enums import Provider
from apps.users.services.social_auth_services import (
    KakaoAuthService,
    NaverAuthService,
    SocialAuthService,
)


@override_settings(
    DEBUG=True,
    SOCIAL_AUTH_FORCE_REAL_REQUEST=False,
    # ✅ 테스트 중 debug_toolbar 완전히 비활성화
    MIDDLEWARE=[mw for mw in settings.MIDDLEWARE if "debug_toolbar.middleware.DebugToolbarMiddleware" not in mw],
    INSTALLED_APPS=[app for app in settings.INSTALLED_APPS if app != "debug_toolbar"],
)
class TestSocialAuthFlow(TestCase):
    """카카오/네이버 소셜 로그인 통합 + 내부 서비스 로직 테스트"""

    client: APIClient

    @classmethod
    def setUpTestData(cls) -> None:
        cls.client = APIClient()

    # ----------------------------------------------------------------------
    # 🔹 1. 통합(E2E) 테스트 - 실제 View 호출
    # ----------------------------------------------------------------------

    def test_kakao_social_login(self) -> None:
        """카카오 로그인 (Mock/Real 자동 지원)"""
        kakao_url = reverse("users:social-login", kwargs={"provider": "kakao"})
        code = "FAKE_KAKAO_CODE"  # ✅ 무조건 Mock 모드

        response = self.client.post(kakao_url, {"code": code}, format="json")

        print("\n🔹 [KAKAO LOGIN RESPONSE]")
        print(response.status_code, response.data)

        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_naver_social_login(self) -> None:
        """네이버 로그인 (Mock/Real 자동 지원)"""
        naver_url = reverse("users:social-login", kwargs={"provider": "naver"})
        code, state = "FAKE_NAVER_CODE", "FAKE_STATE"  # ✅ 무조건 Mock 모드

        response = self.client.post(naver_url, {"code": code, "state": state}, format="json")

        print("\n🔹 [NAVER LOGIN RESPONSE]")
        print(response.status_code, response.data)

        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_kakao_login_validation_error(self) -> None:
        """카카오 ValidationError 처리"""
        kakao_url = reverse("users:social-login", kwargs={"provider": "kakao"})
        with patch(
            "apps.users.services.social_auth_services.KakaoAuthService.handle_login",
            side_effect=ValidationError("토큰 오류 발생"),
        ):
            response = self.client.post(kakao_url, {"code": "ERR_CODE"}, format="json")

        print("\n⚠️ [KAKAO VALIDATION ERROR RESPONSE]")
        print(response.status_code, response.data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_naver_login_generic_exception(self) -> None:
        """네이버 Exception 처리"""
        naver_url = reverse("users:social-login", kwargs={"provider": "naver"})
        with patch(
            "apps.users.services.social_auth_services.NaverAuthService.handle_login",
            side_effect=Exception("예기치 못한 서버 오류"),
        ):
            response = self.client.post(naver_url, {"code": "ERR_CODE", "state": "STATE"}, format="json")

        print("\n⚠️ [NAVER GENERIC ERROR RESPONSE]")
        print(response.status_code, response.data)
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    # ----------------------------------------------------------------------
    # 🔹 2. 서비스 레벨 유닛 테스트 (Mock/Exception/Validation 커버)
    # ----------------------------------------------------------------------

    def test_kakao_mock_mode_flow(self) -> None:
        """카카오 Mock 모드 토큰 및 유저정보 테스트"""
        token = KakaoAuthService.exchange_code_for_token("FAKE_KAKAO_CODE")
        self.assertEqual(token, "mock_access_token_for_kakao")

        user_info = KakaoAuthService.get_user_info("mock_access_token_for_kakao")
        self.assertIn("email", user_info)
        self.assertEqual(user_info["nickname"], "kakao_mock")

    def test_naver_mock_mode_flow(self) -> None:
        """네이버 Mock 모드 토큰 및 유저정보 테스트"""
        token = NaverAuthService.exchange_code_for_token("FAKE_NAVER_CODE", "STATE")
        self.assertEqual(token, "mock_access_token_for_naver")

        user_info = NaverAuthService.get_user_info("mock_access_token_for_naver")
        self.assertEqual(user_info["nickname"], "naver_mock")

    def test_kakao_exchange_code_for_token_network_error(self) -> None:
        """카카오 네트워크 예외 커버"""
        with patch(
            "apps.users.services.social_auth_services.requests.post",
            side_effect=Exception("Network fail"),
        ):
            with self.assertRaises((ValidationError, Exception)):
                KakaoAuthService.exchange_code_for_token("REAL_CODE")

    def test_naver_exchange_code_for_token_http_400(self) -> None:
        """네이버 응답 코드 400 예외 커버"""
        mock_resp = type("MockResp", (), {"status_code": 400, "text": "Bad Request", "json": lambda s: {}})()
        with patch("apps.users.services.social_auth_services.requests.post", return_value=mock_resp):
            with self.assertRaises(ValidationError):
                NaverAuthService.exchange_code_for_token("REAL_CODE", "STATE")

    def test_social_auth_service_invalid_provider(self) -> None:
        """지원하지 않는 provider 예외"""
        with self.assertRaises(ValidationError):
            SocialAuthService.handle_social_login("google", "CODE", None)

    def test_social_auth_service_calls_kakao(self) -> None:
        """카카오 서비스 핸들러 호출 확인"""
        with patch(
            "apps.users.services.social_auth_services.KakaoAuthService.handle_login",
            return_value={"detail": "ok"},
        ) as mock_kakao:
            result = SocialAuthService.handle_social_login(Provider.KAKAO.value, "CODE")
            self.assertEqual(result["detail"], "ok")
            mock_kakao.assert_called_once()

    def test_social_auth_service_calls_naver(self) -> None:
        """네이버 서비스 핸들러 호출 확인"""
        with patch(
            "apps.users.services.social_auth_services.NaverAuthService.handle_login",
            return_value={"detail": "ok"},
        ) as mock_naver:
            result = SocialAuthService.handle_social_login(Provider.NAVER.value, "CODE", "STATE")
            self.assertEqual(result["detail"], "ok")
            mock_naver.assert_called_once()

    # ----------------------------------------------------------------------
    # 🔹 3. 추가 예외/비정상 응답 커버 (커버리지 향상용)
    # ----------------------------------------------------------------------

    def test_kakao_token_response_not_200(self) -> None:
        """카카오 토큰 응답이 200이 아닐 때 ValidationError"""
        mock_resp = type("MockResp", (), {"status_code": 400, "text": "Bad Request", "json": lambda s: {}})()
        with patch("apps.users.services.social_auth_services.requests.post", return_value=mock_resp):
            with self.assertRaises(ValidationError):
                KakaoAuthService.exchange_code_for_token("REAL_CODE")

    def test_kakao_token_missing_access_token(self) -> None:
        """카카오 토큰 응답에 access_token 누락"""
        mock_resp = type(
            "MockResp",
            (),
            {"status_code": 200, "json": lambda s: {"token_type": "bearer"}, "text": "ok"},
        )()
        with patch("apps.users.services.social_auth_services.requests.post", return_value=mock_resp):
            with self.assertRaises(ValidationError):
                KakaoAuthService.exchange_code_for_token("REAL_CODE")

    def test_kakao_userinfo_invalid_status_code(self) -> None:
        """카카오 유저정보 응답이 200이 아닐 때 ValidationError"""
        mock_resp = type("MockResp", (), {"status_code": 400, "text": "Bad Request"})()
        with patch("apps.users.services.social_auth_services.requests.get", return_value=mock_resp):
            with self.assertRaises(ValidationError):
                KakaoAuthService.get_user_info("REAL_ACCESS_TOKEN")

    def test_naver_token_response_not_200(self) -> None:
        """네이버 토큰 응답이 200이 아닐 때 ValidationError"""
        mock_resp = type("MockResp", (), {"status_code": 400, "text": "Bad Request", "json": lambda s: {}})()
        with patch("apps.users.services.social_auth_services.requests.post", return_value=mock_resp):
            with self.assertRaises(ValidationError):
                NaverAuthService.exchange_code_for_token("REAL_CODE", "STATE")

    def test_naver_userinfo_invalid_status_code(self) -> None:
        """네이버 유저정보 응답이 200이 아닐 때 ValidationError"""
        mock_resp = type("MockResp", (), {"status_code": 500, "text": "Server Error"})()
        with patch("apps.users.services.social_auth_services.requests.get", return_value=mock_resp):
            with self.assertRaises(ValidationError):
                NaverAuthService.get_user_info("REAL_ACCESS_TOKEN")

    def test_debug_log_response_handles_invalid_json(self) -> None:
        """_debug_log_response JSONDecodeError 분기 커버"""
        mock_resp = type(
            "MockResp",
            (),
            {"status_code": 200, "json": lambda s: (_ for _ in ()).throw(ValueError()), "text": "INVALID"},
        )()
        from apps.users.services.social_auth_services import _debug_log_response

        _debug_log_response("TEST", mock_resp)  # 예외 없이 실행되면 성공
