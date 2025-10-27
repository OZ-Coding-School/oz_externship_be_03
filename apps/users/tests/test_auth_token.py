from __future__ import annotations

import json
from typing import Dict
from unittest.mock import patch

from django.conf import settings
from django.test import Client, TestCase
from django.urls import reverse


class AuthViewsTest(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.login_url = reverse("users:auth_login")
        self.refresh_url = reverse("users:auth_refresh")

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
