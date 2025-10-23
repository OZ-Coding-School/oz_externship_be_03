from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import Mock, patch

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.test import APIClient

from apps.core.utils.isolated_cache_testcase import IsolatedRedisTestClient
from apps.users.enums import EmailVerificationPurpose
from apps.users.services import email_verification_services as svc
from apps.users.views.email_verification_views import (
    EmailConfirmCodeView,
    EmailSendCodeView,
)
from config.settings.base import (
    GLOBAL_MAX_FAILS,
    MAX_FAIL_ATTEMPTS,
    ONE_TIME_TTL_SECONDS,
    RESEND_COOLDOWN_SECONDS,
)

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------
# 이메일 인증 뷰 테스트
# ---------------------------------------------------------------------
class EmailVerificationViewTests(IsolatedRedisTestClient):
    def setUp(self) -> None:
        super().setUp()
        self.client = APIClient()

        self.send_code_url = reverse("users:email_send_code")
        self.confirm_code_url = reverse("users:email_confirm_code")

        self.valid_send_payload = {
            "email": "example@example.com",
            "purpose": "signup",
        }
        self.valid_confirm_payload = {
            "email": "example@example.com",
            "purpose": "signup",
            "request_id": "SID12345",
            "verification_code": "123456",
        }

        # 권한 완화(테스트 전용)
        EmailSendCodeView.permission_classes = [AllowAny]
        EmailConfirmCodeView.permission_classes = [AllowAny]

    @patch("apps.users.views.email_verification_views.svc.email_send_code")
    def test_send_code_success(self, mock_email_send_code: Mock) -> None:
        """이메일 인증코드 전송 성공"""
        mock_email_send_code.return_value = {
            "request_id": "SID12345",
            "expires_in": 180,
            "cooldown": 30,
            "max_attempts": 5,
        }

        resp = self.client.post(self.send_code_url, self.valid_send_payload, format="json")
        assert resp.status_code == status.HTTP_200_OK, resp.json()
        body = resp.json()

        assert body["detail"] == "인증코드를 발송했습니다."
        assert body["data"]["request_id"] == "SID12345"
        assert isinstance(body["data"]["expires_in"], int)
        assert isinstance(body["data"]["cooldown"], int)
        assert isinstance(body["data"]["max_attempts"], int)

        mock_email_send_code.assert_called_once_with(
            purpose="signup",
            email="example@example.com",
        )

    @patch("apps.users.views.email_verification_views.svc.email_confirm_code")
    def test_confirm_code_success(self, mock_email_confirm_code: Mock) -> None:
        """이메일 인증코드 확인 성공"""
        mock_email_confirm_code.return_value = {
            "verify_token": "VTOK-123",
            "expires_in": 300,
        }

        resp = self.client.post(self.confirm_code_url, self.valid_confirm_payload, format="json")
        assert resp.status_code == status.HTTP_200_OK, resp.json()
        body = resp.json()

        assert body["detail"] == "인증이 완료되었습니다."
        assert body["data"]["verify_token"] == "VTOK-123"
        assert body["data"]["expires_in"] == 300

        mock_email_confirm_code.assert_called_once_with(
            purpose="signup",
            email="example@example.com",
            verification_code="123456",
            request_id="SID12345",
        )


# ---------------------------------------------------------------------
# 이메일 인증 서비스 테스트
# ---------------------------------------------------------------------


class TestEmailVerificationServices(IsolatedRedisTestClient):
    def setUp(self) -> None:
        super().setUp()
        self.email = f"{uuid.uuid4().hex}@example.com"
        self.norm_email = self.email.lower()
        self.purpose = EmailVerificationPurpose.SIGNUP
        self.code_ok = "123456"
        self.code_bad = "000000"

    # -------------------- send_code: 성공 --------------------
    @patch("apps.users.services.email_verification_services.send_mail")
    def test_send_code_success_returns_meta(self, mock_send_mail: Mock) -> None:
        mock_send_mail.return_value = 1  # 성공 가정
        out = svc.email_send_code(email=self.email, purpose=self.purpose)

        assert isinstance(out, dict)
        # request_id는 uuid.hex(32자)라 길이만 검증
        assert isinstance(out.get("request_id"), str) and len(out["request_id"]) == 32
        assert out["expires_in"] == ONE_TIME_TTL_SECONDS
        assert out["cooldown"] == RESEND_COOLDOWN_SECONDS
        assert out["max_attempts"] == MAX_FAIL_ATTEMPTS

        # 메일 발송 호출 확인
        mock_send_mail.assert_called_once()
        args, kwargs = mock_send_mail.call_args
        recipients = kwargs.get("recipient_list") or (args[3] if len(args) >= 4 else None)
        assert recipients == [self.norm_email]

    # -------------------- send_code: 쿨다운 --------------------
    @patch("apps.users.services.email_verification_services.RESEND_COOLDOWN_SECONDS", 60)
    @patch("apps.users.services.email_verification_services.send_mail")
    @patch("apps.users.services.email_verification_services._generate_code", return_value="123456")
    def test_send_code_cooldown_blocks_repeat(self, _mock_code: Mock, mock_send_mail: Mock) -> None:
        mock_send_mail.return_value = 1  # 성공 가정
        first = svc.email_send_code(email=self.email, purpose=self.purpose)
        assert isinstance(first, dict)

        second = svc.email_send_code(email=self.email, purpose=self.purpose)
        assert isinstance(second, Response)
        assert second.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    # -------------------- confirm_code: 성공 --------------------
    @patch("apps.users.services.email_verification_services.GLOBAL_MAX_FAILS", 99)
    @patch("apps.users.services.email_verification_services.issue_verify_token", return_value="VTOK-123")
    @patch("apps.users.services.email_verification_services.send_mail")
    @patch("apps.users.services.email_verification_services._generate_code", return_value="123456")
    def test_confirm_code_success_returns_token(
        self, _mock_code: Mock, mock_send_mail: Mock, _mock_issue: Mock
    ) -> None:
        mock_send_mail.return_value = 1  # 성공 가정

        # 먼저 코드 발송
        meta = svc.email_send_code(email=self.email, purpose=self.purpose)
        assert isinstance(meta, dict)

        # 올바른 코드로 확인
        out = svc.email_confirm_code(
            email=self.email,
            purpose=self.purpose,
            verification_code=self.code_ok,
            request_id=meta["request_id"],
        )
        assert isinstance(out, dict)  # 글로벌락 간섭이 없으므로 dict 보장
        assert out["verify_token"] == "VTOK-123"
        assert isinstance(out["expires_in"], int) and out["expires_in"] > 0

    # -------------------- confirm_code: 잘못된 코드 → 잠금 진행 --------------------
    @patch("apps.users.services.email_verification_services.MAX_FAIL_ATTEMPTS", 2)
    @patch("apps.users.services.email_verification_services.send_mail")
    @patch("apps.users.services.email_verification_services._generate_code", return_value="123456")
    def test_confirm_code_wrong_code_then_lock_progresses(self, _mock_code: Mock, mock_send_mail: Mock) -> None:
        mock_send_mail.return_value = 1  # 성공 가정

        meta = svc.email_send_code(email=self.email, purpose=self.purpose)
        assert isinstance(meta, dict)
        rid = meta["request_id"]

        # 1번째 실패 → 400 기대
        r1 = svc.email_confirm_code(
            email=self.email, purpose=self.purpose, verification_code=self.code_bad, request_id=rid
        )
        assert isinstance(r1, Response)
        assert r1.status_code == status.HTTP_400_BAD_REQUEST

        # 2번째 실패: 구현에 따라 429(임계 도달) 또는 400(임계 초과에서 429)
        r2 = svc.email_confirm_code(
            email=self.email, purpose=self.purpose, verification_code=self.code_bad, request_id=rid
        )
        assert isinstance(r2, Response)

        if r2.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            locked: Response = r2
        else:
            # 3번째 실패에서 429 기대
            r3 = svc.email_confirm_code(
                email=self.email, purpose=self.purpose, verification_code=self.code_bad, request_id=rid
            )
            assert isinstance(r3, Response)
            locked = r3

        assert locked.status_code == status.HTTP_429_TOO_MANY_REQUESTS

        # 락 지속성 확인: 추가 시도도 429 유지
        r_next = svc.email_confirm_code(
            email=self.email, purpose=self.purpose, verification_code=self.code_bad, request_id=rid
        )
        assert isinstance(r_next, Response)
        assert r_next.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    # -------------------- confirm_code: request_id 누락/만료 --------------------
    def test_confirm_code_missing_request_id(self) -> None:
        res = svc.email_confirm_code(
            email=self.email,
            purpose=self.purpose,
            verification_code=self.code_ok,
            request_id="UNKNOWN_SID",
        )
        assert isinstance(res, Response)
        # 구현상 404로 내려줌
        assert res.status_code == status.HTTP_404_NOT_FOUND

    # -------------------- 글로벌 실패 잠금 --------------------
    @patch("apps.users.services.email_verification_services.GLOBAL_MAX_FAILS", 2)
    @patch("apps.users.services.email_verification_services.send_mail")
    @patch("apps.users.services.email_verification_services._generate_code", return_value="123456")
    def test_global_fail_lock_after_many_failures(self, _mock_code: Mock, mock_send_mail: Mock) -> None:
        """
        잘못된 코드 실패를 반복하면 글로벌 실패 카운터가 쌓여 이후 선락(429)이 걸린다.
        같은 request_id로도 글로벌 카운트는 누적됨.
        """
        mock_send_mail.return_value = 1  # 성공 가정

        # 단 한 번 발송하여 request_id 확보
        meta = svc.email_send_code(email=self.email, purpose=self.purpose)
        assert isinstance(meta, dict)
        rid = meta["request_id"]

        # 1) 첫 실패 → 400
        r1 = svc.email_confirm_code(
            email=self.email, purpose=self.purpose, verification_code=self.code_bad, request_id=rid
        )
        assert isinstance(r1, Response) and r1.status_code == status.HTTP_400_BAD_REQUEST

        # 2) 두 번째 실패: 구현에 따라 429 또는 400
        r2 = svc.email_confirm_code(
            email=self.email, purpose=self.purpose, verification_code=self.code_bad, request_id=rid
        )
        assert isinstance(r2, Response)
        if r2.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            locked: Response = r2
        else:
            # 3) 한 번 더 실패 → 429
            r3 = svc.email_confirm_code(
                email=self.email, purpose=self.purpose, verification_code=self.code_bad, request_id=rid
            )
            assert isinstance(r3, Response)
            locked = r3

        assert locked.status_code == status.HTTP_429_TOO_MANY_REQUESTS
