from __future__ import annotations

import json
import random
from datetime import date
from typing import Any, ClassVar, Dict, Final
from unittest.mock import Mock, patch
from uuid import uuid4

from django.conf import settings
from django.test import Client, TestCase
from django.urls import reverse
from rest_framework import serializers

from apps.users.models.user import User as UserModel
from apps.users.services.auth_services import (
    authenticate_and_issue_tokens,
    refresh_access_token,
)
from apps.users.views.auth_views import (
    _validate_login_payload,
    _validate_refresh_payload,
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

    @classmethod
    def setUpTestData(cls) -> None:
        cls.login_url = reverse("users:auth_login")
        cls.refresh_url = reverse("users:auth_refresh")

    def setUp(self) -> None:
        self.client = Client()

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

    # ------------------------------
    # /auth/refresh (쿠키 전용)
    # ------------------------------
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

    def test_refresh_missing_token_returns_400(self) -> None:
        resp = self.client.post(self.refresh_url, data=json.dumps({}), content_type="application/json")
        self.assertEqual(resp.status_code, 400)
        body = json.loads(resp.content.decode())
        self.assertEqual(body["error"], "리프레시 토큰이 필요합니다.")

    def test_refresh_invalid_format_cookie_returns_400(self) -> None:
        cookie_name = settings.AUTH_REFRESH_COOKIE_NAME
        self.client.cookies[cookie_name] = "invalidtoken"

        resp = self.client.post(self.refresh_url, data=json.dumps({}), content_type="application/json")
        self.assertEqual(resp.status_code, 400)
        body = json.loads(resp.content.decode())
        self.assertEqual(body["error"], "refresh 토큰 형식이 올바르지 않습니다.")

    def test_refresh_cookie_service_reject_returns_400(self) -> None:
        cookie_name = settings.AUTH_REFRESH_COOKIE_NAME
        self.client.cookies[cookie_name] = "a.b.c"

        with patch(
            "apps.users.views.auth_views.refresh_access_token",
            side_effect=PermissionError,
        ):
            resp = self.client.post(self.refresh_url, data=json.dumps({}), content_type="application/json")

        self.assertEqual(resp.status_code, 400)
        body = json.loads(resp.content.decode())
        self.assertEqual(body["error"], "유효하지 않은 리프레시 토큰입니다.")


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

        tokens: Dict[str, str] = authenticate_and_issue_tokens(
            email="  user@example.com  ",
            password=DEFAULT_PWD,
        )
        assert "access" in tokens and tokens["access"]
        assert "refresh" in tokens and tokens["refresh"]

        call_kwargs = mock_auth.call_args.kwargs
        assert call_kwargs["email"] == "user@example.com"
        assert call_kwargs["password"] == DEFAULT_PWD

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

    def test_refresh_access_token_success(self) -> None:
        from rest_framework_simplejwt.tokens import RefreshToken

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

    def test_validate_refresh_payload_paths(self) -> None:
        payload = {"refresh": "  a.b.c  "}
        _validate_refresh_payload(payload)
        self.assertEqual(payload["refresh"], "a.b.c")

        with self.assertRaises(serializers.ValidationError):
            _validate_refresh_payload({"refresh": "   "})

        with self.assertRaises(serializers.ValidationError):
            _validate_refresh_payload({"refresh": "invalidtoken"})

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
