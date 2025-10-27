from __future__ import annotations

import os
from typing import Any, cast
from unittest.mock import patch

import jwt
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.response import Response

from apps.users.enums import EmailVerificationPurpose, PhoneVerificationPurpose
from apps.users.utils.verify_token import (
    REDIS_JTI_PREFIX,
    _jti_key,
    issue_verify_token,
    verify_and_consume,
)


def _decode_no_verify(token: str) -> Any:
    """JWT 서명/만료 검증 없이 payload만 열람 (테스트 전용)"""
    return jwt.decode(token, options={"verify_signature": False, "verify_exp": False})


class VerifyTokenUtilsTests(TestCase):
    def setUp(self) -> None:
        cache.clear()

    def tearDown(self) -> None:
        cache.clear()

    # ------------------------------------------------------------------
    # issue_verify_token()
    # ------------------------------------------------------------------
    def test_issue_verify_token_sets_cache_and_returns_jwt(self) -> None:
        token = issue_verify_token(
            sub="01012345678",
            to="01012345678",
            purpose=PhoneVerificationPurpose.SIGNUP,
        )

        payload = _decode_no_verify(token)
        self.assertEqual(payload["sub"], "01012345678")
        self.assertEqual(payload["to"], "01012345678")
        self.assertEqual(payload["purpose"], PhoneVerificationPurpose.SIGNUP)
        self.assertIn("jti", payload)
        self.assertIn("exp", payload)

        jti_key = _jti_key(payload["purpose"], payload["jti"])
        self.assertEqual(cache.get(jti_key), 1)

    # ------------------------------------------------------------------
    # verify_and_consume()
    # ------------------------------------------------------------------
    def test_verify_and_consume_success_then_cannot_reuse(self) -> None:
        token = issue_verify_token(
            sub="01099999999",
            to="01099999999",
            purpose=PhoneVerificationPurpose.CHANGE_PHONE,
        )

        # 1회차: 성공
        result = verify_and_consume(
            token,
            expected_purpose=PhoneVerificationPurpose.CHANGE_PHONE,
            expected_sub="01099999999",
        )
        self.assertIsInstance(result, dict)
        self.assertEqual(result["sub"], "01099999999")
        self.assertEqual(result["purpose"], PhoneVerificationPurpose.CHANGE_PHONE)

        # 2회차: 재사용 불가
        result2 = verify_and_consume(
            token,
            expected_purpose=PhoneVerificationPurpose.CHANGE_PHONE,
            expected_sub="01099999999",
        )
        self.assertIsInstance(result2, Response)
        resp2 = cast(Response, result2)
        self.assertEqual(resp2.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_verify_wrong_purpose_returns_401(self) -> None:
        """토큰 목적이 다른 경우"""
        token = issue_verify_token(
            sub="user@example.com",
            to="user@example.com",
            purpose=EmailVerificationPurpose.SIGNUP,
        )

        # 잘못된 목적 기대
        result = verify_and_consume(
            token,
            expected_purpose=EmailVerificationPurpose.RESET_PASSWORD,
            expected_sub="user@example.com",
        )
        self.assertIsInstance(result, Response)
        resp = cast(Response, result)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_verify_wrong_sub_returns_401(self) -> None:
        """sub 불일치"""
        token = issue_verify_token(
            sub="user@example.com",
            to="user@example.com",
            purpose=EmailVerificationPurpose.RESET_PASSWORD,
        )

        result = verify_and_consume(
            token,
            expected_purpose=EmailVerificationPurpose.RESET_PASSWORD,
            expected_sub="other@example.com",
        )
        self.assertIsInstance(result, Response)
        resp = cast(Response, result)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_verify_expired_token_returns_401(self) -> None:
        """
        발급(now=1000), 만료=1001
        검증(now=1002) -> ExpiredSignatureError 발생
        """
        with patch("apps.users.utils.verify_token.time.time", return_value=1000):
            token = issue_verify_token(
                sub="01033334444",
                to="01033334444",
                purpose=PhoneVerificationPurpose.SIGNUP,
            )

        with patch("apps.users.utils.verify_token.time.time", return_value=1002):
            result = verify_and_consume(
                token,
                expected_purpose=PhoneVerificationPurpose.SIGNUP,
                expected_sub="01033334444",
            )

        self.assertIsInstance(result, Response)
        resp = cast(Response, result)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_verify_invalid_token_returns_401(self) -> None:
        """JWT 형식이 아닌 문자열"""
        result = verify_and_consume(
            token="not-a-jwt",
            expected_purpose=PhoneVerificationPurpose.SIGNUP,
            expected_sub="01011112222",
        )
        self.assertIsInstance(result, Response)
        resp = cast(Response, result)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    @override_settings(
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            }
        }
    )
    def test_cache_timeout_matches_exp(self) -> None:
        """
        캐시 TTL이 환경변수 VERIFY_TOKEN_EXPIRES_SECONDS와 동일하게 동작하는지 확인.
        LocMemCache를 강제하고, verify_token/locmem 양쪽 time을 패치해 시간 경과를 시뮬레이션.
        """
        expire_seconds = int(os.getenv("VERIFY_TOKEN_EXPIRES_SECONDS", "600"))

        # 1) 발급 시각 고정
        with patch("apps.users.utils.verify_token.time.time", return_value=10_000):
            token = issue_verify_token(
                sub="subj",
                to="dest",
                purpose=PhoneVerificationPurpose.FIND_EMAIL,
            )
            payload = _decode_no_verify(token)
            jti_key = _jti_key(payload["purpose"], payload["jti"])
            self.assertEqual(cache.get(jti_key), 1)

        # 2) TTL + 1초 경과 시점으로 이동
        late_time = 10_000 + expire_seconds + 1

        # verify_token 모듈과 LocMemCache 모듈의 time을 모두 패치
        patchers = [
            patch("apps.users.utils.verify_token.time.time", return_value=late_time),
            patch("django.core.cache.backends.locmem.time.time", return_value=late_time),
        ]

        with patchers[0], patchers[1]:
            # LocMemCache는 접근 시 만료를 평가하므로 한 번 접근해서 만료 트리거
            _ = cache.get(jti_key)
            self.assertIsNone(cache.get(jti_key))
