from __future__ import annotations

import json
import random
from datetime import date, timedelta
from typing import Any, ClassVar, Dict, Final
from unittest.mock import Mock, patch
from uuid import uuid4

from django.conf import settings
from django.http import HttpRequest
from django.test import TestCase
from django.urls import reverse
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.test import APIClient
from rest_framework_simplejwt.exceptions import (
    ExpiredTokenError,
    InvalidToken,
    TokenError,
)
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.users.models.user import User as UserModel
from apps.users.services.auth_services import (
    authenticate_and_issue_tokens,
    refresh_access_token,
)
from apps.users.utils.jwt import coerce_samesite, extract_bearer_token, is_jwt_like
from apps.users.views.auth_views import (
    _validate_login_payload,
)

# ---------------------------------------------------------------------
# 공통 상수/헬퍼
# ---------------------------------------------------------------------

DEFAULT_PWD: Final[str] = "Passw0rd!"


def make_user(
    *,
    email: str | None = None,
    password: str = DEFAULT_PWD,
    name: str = "홍길동",
    nickname: str | None = None,
    phone_number: str | None = None,
    gender: str = "M",
    birthday: date = date(1990, 1, 1),
    is_active: bool = True,
) -> UserModel:
    """
    테스트 유저 생성
    """
    suffix = uuid4().hex[:6]
    if email is None:
        email = f"user{suffix}@example.com"
    if nickname is None:
        nickname = f"nick{suffix}"
    if phone_number is None:
        phone_number = f"010-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}"

    user = UserModel.objects.create_user(
        email=email,
        password=password,
        name=name,
        nickname=nickname,
        phone_number=phone_number,
        gender=gender,
        birthday=birthday,
    )
    if user.is_active != is_active:
        user.is_active = is_active
        user.save(update_fields=["is_active"])
    return user


# ---------------------------------------------------------------------
# 뷰 테스트
# ---------------------------------------------------------------------


class AuthViewsTest(TestCase):
    login_url: ClassVar[str]
    refresh_url: ClassVar[str]
    logout_url: ClassVar[str]
    user: UserModel
    client: APIClient

    @classmethod
    def setUpTestData(cls) -> None:
        cls.login_url = reverse("users:auth_login")
        cls.refresh_url = reverse("users:auth_refresh")
        cls.logout_url = reverse("users:auth_logout")
        cls.user = make_user()

    def setUp(self) -> None:
        self.client = APIClient()

        self.access_token, self.refresh_token = self.get_tokens()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(self.access_token)}")

    def get_tokens(self) -> tuple[AccessToken, RefreshToken]:
        """
        토큰을 생성하고 만료 시간을 설정하는 공통 메서드
        """
        refresh_token = RefreshToken.for_user(self.user)
        access_token = refresh_token.access_token

        refresh_token.set_exp(lifetime=timedelta(hours=1))
        access_token.set_exp(lifetime=timedelta(hours=1))

        return access_token, refresh_token

    # ------------------------------
    # /auth/login
    # ------------------------------
    def test_login_success_sets_cookie_and_returns_access(self) -> None:
        payload = {"email": "User@Example.COM", "password": "pass1234!"}
        fake_tokens: Dict[str, str] = {
            "access": "access.jwt.token",
            "refresh": "refresh.jwt.token",
        }

        with patch(
            "apps.users.views.auth_views.authenticate_and_issue_tokens",
            return_value=fake_tokens,
        ):
            resp = self.client.post(
                self.login_url,
                data=json.dumps(payload),
                content_type="application/json",
            )

        self.assertEqual(resp.status_code, 201)
        body = json.loads(resp.content.decode())
        self.assertEqual(body["detail"], "토큰이 발급되었습니다.")
        self.assertEqual(body["data"]["access"], fake_tokens["access"])

        # 쿠키로 검증
        cookie_name = settings.AUTH_REFRESH_COOKIE_NAME
        self.assertIn(cookie_name, resp.cookies)
        c = resp.cookies[cookie_name]
        out = c.output(header="")

        self.assertEqual(str(settings.AUTH_REFRESH_COOKIE_MAX_AGE), str(c["max-age"]))

        samesite = getattr(settings, "AUTH_REFRESH_COOKIE_SAMESITE", None)
        if samesite is not None:
            self.assertEqual(str(c["samesite"]).lower(), str(samesite).lower())

        if settings.AUTH_REFRESH_COOKIE_HTTPONLY:
            self.assertIn("httponly", out.lower())
        if settings.AUTH_REFRESH_COOKIE_SECURE:
            self.assertIn("secure", out.lower())

    def test_login_invalid_credentials_returns_400(self) -> None:
        with patch(
            "apps.users.views.auth_views.authenticate_and_issue_tokens",
            side_effect=PermissionError,
        ):
            resp = self.client.post(
                self.login_url,
                data=json.dumps({"email": "a@a.com", "password": "wrong"}),
                content_type="application/json",
            )
        self.assertEqual(resp.status_code, 400)
        body = json.loads(resp.content.decode())
        self.assertEqual(body["error"], "이메일 또는 비밀번호가 올바르지 않습니다.")

    def test_login_normalizes_email_domain_to_lowercase(self) -> None:
        with patch(
            "apps.users.views.auth_views.authenticate_and_issue_tokens",
            return_value={"access": "a", "refresh": "r"},
        ) as mocked:
            resp = self.client.post(
                self.login_url,
                data=json.dumps({"email": "USER@EXAMPLE.COM", "password": "pass1234!"}),
                content_type="application/json",
            )
        self.assertEqual(resp.status_code, 201)
        kwargs = mocked.call_args.kwargs
        self.assertTrue(kwargs["email"].endswith("@example.com"))

    def test_login_rejects_password_with_leading_or_trailing_spaces(self) -> None:
        payload = {"email": "user@example.com", "password": " pass1234! "}
        resp = self.client.post(self.login_url, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(resp.status_code, 400)
        body = json.loads(resp.content.decode())
        self.assertTrue("password" in body or "error" in body)

    def test_login_missing_email_returns_400_by_schema(self) -> None:
        resp = self.client.post(
            self.login_url,
            data=json.dumps({"password": "pass1234!"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        body = json.loads(resp.content.decode())
        self.assertIn("email", body)

    def test_refresh_uses_cookie_when_present(self) -> None:
        cookie_name = settings.AUTH_REFRESH_COOKIE_NAME
        self.client.cookies[cookie_name] = "header.payload.signature"

        with patch(
            "apps.users.views.auth_views.refresh_access_token",
            return_value="new.access.jwt",
        ) as mocked:
            resp = self.client.post(self.refresh_url, data=json.dumps({}), content_type="application/json")

        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.content.decode())
        self.assertEqual(body["detail"], "액세스 토큰이 재발급되었습니다.")
        self.assertEqual(body["data"]["access"], "new.access.jwt")
        mocked.assert_called_once_with(refresh_token="header.payload.signature")

    # ------------------------------
    # /auth/logout
    # ------------------------------
    def test_logout_success(self) -> None:
        payload = {"email": self.user.email, "password": DEFAULT_PWD}

        self.refresh_token.set_exp(lifetime=timedelta(hours=1))
        self.access_token.set_exp(lifetime=timedelta(hours=1))

        fake_tokens: Dict[str, str] = {
            "access": str(self.access_token),
            "refresh": str(self.refresh_token),
        }

        with patch(
            "apps.users.views.auth_views.authenticate_and_issue_tokens",
            return_value=fake_tokens,
        ):
            # 로그인 후 리프레시 토큰 쿠키 설정
            resp = self.client.post(
                self.login_url,
                data=json.dumps(payload),
                content_type="application/json",
            )

        # 로그인 후 리프레시 토큰을 쿠키에 설정
        self.client.cookies[settings.AUTH_REFRESH_COOKIE_NAME] = str(self.refresh_token)

        # 액세스 토큰을 Authorization 헤더에 설정하여 인증된 상태로 만든다.
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(self.access_token)}")

        with patch("apps.users.views.auth_views.RefreshToken.blacklist", return_value=None):  # mock 처리
            # 로그아웃 요청
            resp = self.client.post(self.logout_url, data=json.dumps({}), content_type="application/json")

        # 정상적으로 로그아웃 처리된 경우
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.content.decode())["detail"], "로그아웃이 완료되었습니다.")

        cookie = resp.cookies.get(settings.AUTH_REFRESH_COOKIE_NAME)
        if cookie:
            self.assertEqual(cookie.value, "")  # 쿠키가 빈 값으로 설정되었는지 확인
        else:
            self.fail(f"쿠키 '{settings.AUTH_REFRESH_COOKIE_NAME}'가 삭제되지 않았습니다.")

    def test_logout_invalid_token_returns_401(self) -> None:
        # 잘못된 토큰인 경우
        refresh_token = RefreshToken.for_user(self.user)
        access_token = refresh_token.access_token

        refresh_token.set_exp(lifetime=timedelta(hours=1))
        access_token.set_exp(lifetime=timedelta(hours=1))

        self.client.cookies[settings.AUTH_REFRESH_COOKIE_NAME] = str(refresh_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(access_token)}")
        with patch("apps.users.views.auth_views.RefreshToken.blacklist", side_effect=InvalidToken):
            resp = self.client.post(self.logout_url, data=json.dumps({}), content_type="application/json")

        # 유효하지 않은 토큰 오류
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(json.loads(resp.content.decode())["error"], "유효하지 않은 토큰입니다.")

    def test_logout_expired_token_returns_200(self) -> None:
        # 만료된 토큰인 경우
        refresh_token = RefreshToken.for_user(self.user)
        access_token = refresh_token.access_token

        refresh_token.set_exp(lifetime=timedelta(hours=1))
        access_token.set_exp(lifetime=timedelta(hours=1))

        with patch("apps.users.views.auth_views.RefreshToken.blacklist", side_effect=ExpiredTokenError):
            resp = self.client.post(self.logout_url, data=json.dumps({}), content_type="application/json")

        # 만료된 토큰 오류
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.content.decode())["detail"], "세션이 유효하지 않습니다. 다시 로그인해주세요.")

    def test_logout_already_logged_out_returns_200(self) -> None:
        refresh_token = RefreshToken.for_user(self.user)
        access_token = refresh_token.access_token

        refresh_token.set_exp(lifetime=timedelta(hours=1))
        # 이미 로그아웃된 상태
        self.client.cookies[settings.AUTH_REFRESH_COOKIE_NAME] = str(refresh_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(access_token)}")  # APIClient로 인증된 상태 설정

        with patch.object(
            RefreshToken,
            "blacklist",
            side_effect=TokenError("세션이 유효하지 않습니다. 다시 로그인해주세요."),
        ):
            resp = self.client.post(
                self.logout_url,
                data=json.dumps({}),
                content_type="application/json",
            )

        # 이미 로그아웃된 경우 처리
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.content.decode())["detail"], "세션이 유효하지 않습니다. 다시 로그인해주세요.")

    def test_logout_not_logged_in_returns_200(self) -> None:
        # 로그인이 안 된 상태
        resp = self.client.post(self.logout_url, data=json.dumps({}), content_type="application/json")

        # 로그인되지 않은 상태에서의 처리
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.content.decode())["detail"], "세션이 유효하지 않습니다. 다시 로그인해주세요.")


# ---------------------------------------------------------------------
# 서비스 테스트
# ---------------------------------------------------------------------
class AuthServiceTests(TestCase):
    user_id: ClassVar[int]

    @classmethod
    def setUpTestData(cls) -> None:
        u = make_user()
        cls.user_id = u.id

    def setUp(self) -> None:
        self.user: UserModel = UserModel.objects.get(pk=self.user_id)

    @patch("apps.users.services.auth_services.authenticate")
    def test_authenticate_and_issue_tokens_success(self, mock_auth: Mock) -> None:
        mock_auth.return_value = self.user

        tokens = authenticate_and_issue_tokens(
            email="  user@example.com  ",
            password=DEFAULT_PWD,
        )
        assert "access" in tokens and tokens["access"]
        assert "refresh" in tokens and tokens["refresh"]

        call_kwargs = mock_auth.call_args.kwargs
        assert call_kwargs["email"] == "user@example.com"
        assert call_kwargs["password"] == DEFAULT_PWD

    # ==============================
    # authenticate_and_issue_tokens 예외 처리 테스트
    # ==============================
    @patch("apps.users.services.auth_services.authenticate")
    def test_authenticate_and_issue_tokens_invalid_credentials(self, mock_auth: Mock) -> None:
        mock_auth.return_value = None
        with self.assertRaises(PermissionError):
            authenticate_and_issue_tokens(email="user@example.com", password="wrong!")

    @patch("apps.users.services.auth_services.authenticate")
    def test_authenticate_and_issue_tokens_inactive_user(self, mock_auth: Mock) -> None:
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        mock_auth.return_value = self.user

        with self.assertRaises(PermissionError):
            authenticate_and_issue_tokens(email="user@example.com", password=DEFAULT_PWD)

    # ==============================
    # refresh_access_token 성공 및 실패 테스트
    # ==============================
    def test_refresh_access_token_success(self) -> None:
        refresh = str(RefreshToken.for_user(self.user))
        new_access = refresh_access_token(refresh_token=refresh)
        assert isinstance(new_access, str) and len(new_access) > 10

    def test_refresh_access_token_invalid_token(self) -> None:
        with self.assertRaises(PermissionError):
            refresh_access_token(refresh_token="not.a.valid.token")


# ---------------------------------------------------------------------
# 유효성 함수 커버
# ---------------------------------------------------------------------


class AuthValidatorsUnitTest(TestCase):
    def test_validate_login_payload_email_normalization_and_password_space_rejection(self) -> None:
        _validate_login_payload({"email": "USER@EXAMPLE.COM", "password": "pass"})

        with self.assertRaises(serializers.ValidationError):
            _validate_login_payload({"email": "user@example.com", "password": " pass "})

        ok_payload: Dict[str, Any] = {"email": " USER@EXAMPLE.COM ", "password": "pass"}
        _validate_login_payload(ok_payload)
        self.assertEqual(ok_payload["email"], "USER@example.com")

    def test_validate_login_payload_missing_email(self) -> None:
        # email이 공백/미입력일 때
        with self.assertRaises(serializers.ValidationError):
            _validate_login_payload({"email": "   ", "password": "pass1234!"})

    def test_validate_login_payload_missing_password(self) -> None:
        # password가 미입력일 때
        with self.assertRaises(serializers.ValidationError):
            _validate_login_payload({"email": "user@example.com", "password": ""})

    def test_validate_login_payload_invalid_email_format(self) -> None:
        # 잘못된 이메일 형식
        with self.assertRaises(serializers.ValidationError):
            _validate_login_payload({"email": "not-an-email", "password": "pass1234!"})


class TestJwtUtils(TestCase):

    def test_valid_samesite_values(self) -> None:
        self.assertEqual(coerce_samesite("Lax"), "Lax")
        self.assertEqual(coerce_samesite("Strict"), "Strict")
        self.assertEqual(coerce_samesite("None"), "None")

    def test_false_value(self) -> None:
        self.assertEqual(coerce_samesite(False), False)

    def test_invalid_values(self) -> None:
        self.assertIsNone(coerce_samesite("Invalid"))
        self.assertIsNone(coerce_samesite(None))

    def test_valid_jwt(self) -> None:
        self.assertTrue(is_jwt_like("valid.jwt.token"))

    def test_invalid_jwt(self) -> None:
        self.assertFalse(is_jwt_like("invalid.token"))
        self.assertFalse(is_jwt_like("token.withoutparts"))
        self.assertFalse(is_jwt_like("part1.part2"))
        self.assertFalse(is_jwt_like(""))

    def test_empty_string(self) -> None:
        self.assertFalse(is_jwt_like(""))

    def test_missing_parts(self) -> None:
        self.assertFalse(is_jwt_like("part1.part2"))

    def test_extract_valid_token(self) -> None:
        request = HttpRequest()
        # 요청의 META에 'Authorization' 헤더를 설정
        request.META["HTTP_AUTHORIZATION"] = "Bearer valid_token_string"

        # HttpRequest를 Request로 래핑
        drf_request = Request(request)

        token = extract_bearer_token(drf_request)
        self.assertEqual(token, "valid_token_string")

    def test_extract_invalid_token(self) -> None:
        request = HttpRequest()
        request.META["HTTP_AUTHORIZATION"] = "InvalidToken"

        drf_request = Request(request)

        token = extract_bearer_token(drf_request)
        self.assertIsNone(token)

    def test_no_authorization_header(self) -> None:
        request = HttpRequest()
        request.META["HTTP_AUTHORIZATION"] = ""

        drf_request = Request(request)

        token = extract_bearer_token(drf_request)
        self.assertIsNone(token)
