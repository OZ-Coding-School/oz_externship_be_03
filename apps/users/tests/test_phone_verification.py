from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status

from apps.core.utils.isolated_cache_testcase import IsolatedRedisTestClient
from apps.users.enums import PhoneVerificationPurpose
from apps.users.services.phone_verification_services import (
    _global_lock_key,
    _lock_key,
    _pending_key,
)
from apps.users.utils.phone_normalize import normalize_kr_phone

User = get_user_model()


class BasePhoneVerificationTests(IsolatedRedisTestClient):
    """
    공통 시나리오.
    인증 필요한 경우 auth만 오버라이드.
    """

    # 서브클래스에서 채우는 필드
    PURPOSE: PhoneVerificationPurpose
    SEND_URL_NAME: str
    CONFIRM_URL_NAME: str
    PHONE: str = "01012345678"
    REQUEST_ID: str = "SID12345"
    CODE: str = "123456"

    # Base 테스트는 스킵
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        required = ("PURPOSE", "SEND_URL_NAME", "CONFIRM_URL_NAME")
        if cls is BasePhoneVerificationTests or any(not hasattr(cls, k) for k in required):
            raise unittest.SkipTest("Abstract base for phone verification tests")

    # ---------- override 지점 ----------
    def auth(self) -> None:
        """공개 엔드포인트 기본 동작: 아무것도 안 함 (no-op)"""
        return

    # ---------- 공통 셋업 ----------
    def setUp(self) -> None:
        super().setUp()
        self.send_code_url = reverse(f"users:{self.SEND_URL_NAME}")
        self.confirm_code_url = reverse(f"users:{self.CONFIRM_URL_NAME}")
        self.valid_phone_data = {"phone_number": self.PHONE}
        self.valid_confirm_data = {
            "phone_number": self.PHONE,
            "request_id": self.REQUEST_ID,
            "code": self.CODE,
        }

    # ---------- 헬퍼 ----------
    def seed_pending(self) -> None:
        to = normalize_kr_phone(self.valid_confirm_data["phone_number"])
        key = _pending_key(
            subject=to,
            purpose=self.PURPOSE,
            sid=self.valid_confirm_data["request_id"],
        )
        cache.set(key, normalize_kr_phone(self.PHONE), timeout=600)

    # ---------- 공통 테스트 ----------
    @patch("apps.users.services.phone_verification_services._twilio")
    def send_code_success(self, mock_twilio: Mock) -> None:
        """휴대폰 인증코드 전송 성공"""
        self.auth()  # 항상 호출; 공개 API면 no-op, 인증 필요 API면 로그인됨
        mock_twilio.verify.v2.services.return_value.verifications.create.return_value.sid = self.REQUEST_ID

        response = self.client.post(self.send_code_url, self.valid_phone_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["detail"], "인증코드를 발송했습니다.")
        self.assertEqual(data["data"]["request_id"], self.REQUEST_ID)
        self.assertIsInstance(data["data"]["expires_in"], int)
        self.assertIsInstance(data["data"]["cooldown"], int)
        self.assertIsInstance(data["data"]["max_attempts"], int)

    @patch("apps.users.services.phone_verification_services._twilio")
    def send_code_resend_cooldown(self, mock_twilio: Mock) -> None:
        """재전송 쿨다운 중 요청 시 429"""
        self.auth()

        mock_twilio.verify.v2.services.return_value.verifications.create.return_value.sid = self.REQUEST_ID

        # 1차 전송: 성공
        r1 = self.client.post(self.send_code_url, self.valid_phone_data, format="json")
        self.assertEqual(r1.status_code, status.HTTP_200_OK)

        # 2차 전송: 쿨다운으로 429 반환
        r2 = self.client.post(self.send_code_url, self.valid_phone_data, format="json")
        self.assertEqual(r2.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn("error", r2.json())

    @patch("apps.users.services.phone_verification_services.issue_verify_token", return_value="mocked-token")
    @patch("apps.users.services.phone_verification_services._twilio")
    def confirm_code_success(self, mock_twilio: Mock, _mock_issue: Mock) -> None:
        """휴대폰 인증코드 검증 성공"""
        self.auth()
        mock_twilio.verify.v2.services.return_value.verification_checks.create.return_value.status = "approved"
        self.seed_pending()

        response = self.client.post(self.confirm_code_url, self.valid_confirm_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["detail"], "인증이 완료되었습니다.")
        self.assertEqual(data["data"]["verify_token"], "mocked-token")
        self.assertIsInstance(data["data"]["expires_in"], int)

    @patch("apps.users.services.phone_verification_services._twilio")
    def confirm_code_invalid_request_id(self, mock_twilio: Mock) -> None:
        """잘못된 request_id로 요청 시 404"""
        self.auth()
        mock_twilio.verify.v2.services.return_value.verification_checks.create.return_value.status = "approved"

        response = self.client.post(self.confirm_code_url, self.valid_confirm_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.json())

    @patch("apps.users.services.phone_verification_services._twilio")
    def confirm_code_invalid_code(self, mock_twilio: Mock) -> None:
        """인증코드 불일치 시 400"""
        self.auth()
        mock_twilio.verify.v2.services.return_value.verification_checks.create.return_value.status = "pending"
        self.seed_pending()

        response = self.client.post(self.confirm_code_url, self.valid_confirm_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.json())

    @patch("apps.users.services.phone_verification_services._twilio")
    def confirm_code_locked(self, mock_twilio: Mock) -> None:
        """락이 걸린 번호/목적에 대해 429"""
        self.auth()
        mock_twilio.verify.v2.services.return_value.verification_checks.create.return_value.status = "approved"
        to = normalize_kr_phone(self.PHONE)
        cache.set(_global_lock_key(to), "1", timeout=60)
        cache.set(_lock_key(to, self.PURPOSE), "1", timeout=60)

        response = self.client.post(self.confirm_code_url, self.valid_confirm_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn("error", response.json())


# =========================
# 회원가입용 인증 테스트
# =========================
class SignupPhoneVerificationSmokeTests(BasePhoneVerificationTests):
    PURPOSE = PhoneVerificationPurpose.SIGNUP
    SEND_URL_NAME = "phone_signup_send_code"
    CONFIRM_URL_NAME = "phone_signup_confirm_code"

    def test_send_code_success_for_signup(self) -> None:
        self.send_code_success()

    def test_confirm_code_success_for_signup(self) -> None:
        self.confirm_code_success()

    def test_send_code_resend_cooldown_for_signup(self) -> None:
        self.send_code_resend_cooldown()

    def test_confirm_code_invalid_request_id_for_signup(self) -> None:
        self.confirm_code_invalid_request_id()

    def test_confirm_code_invalid_code_for_signup(self) -> None:
        self.confirm_code_invalid_code()

    def test_confirm_code_locked_for_signup(self) -> None:
        self.confirm_code_locked()


# =========================
# 이메일 찾기용 인증 테스트
# =========================
class FindEmailPhoneVerificationSmokeTests(BasePhoneVerificationTests):
    PURPOSE = PhoneVerificationPurpose.FIND_EMAIL
    SEND_URL_NAME = "find_email_send_code"
    CONFIRM_URL_NAME = "find_email_confirm_code"

    def test_send_code_success_for_find_email(self) -> None:
        self.send_code_success()

    def test_confirm_code_success_for_find_email(self) -> None:
        self.confirm_code_success()

    def test_send_code_resend_cooldown_for_find_email(self) -> None:
        self.send_code_resend_cooldown()

    def test_confirm_code_invalid_request_id_for_find_email(self) -> None:
        self.confirm_code_invalid_request_id()

    def test_confirm_code_invalid_code_for_find_email(self) -> None:
        self.confirm_code_invalid_code()

    def test_confirm_code_locked_for_find_email(self) -> None:
        self.confirm_code_locked()


# =========================
# 비밀번호 변경용 인증 테스트
# =========================
class ChangePhoneVerificationViewTests(BasePhoneVerificationTests):
    PURPOSE = PhoneVerificationPurpose.CHANGE_PHONE
    SEND_URL_NAME = "change_phone_send_code"
    CONFIRM_URL_NAME = "change_phone_confirm_code"

    def setUp(self) -> None:
        super().setUp()

        # 인증 사용자 생성
        self.user = User.objects.create_user(
            email="user@example.com",
            password="pass1234!",
            nickname="ozdev",
            name="홍길동",
            phone_number="01011112222",
            birthday="2000-01-01",
            gender="M",
        )

    def auth(self) -> None:  # 오버라이드
        self.client.force_authenticate(user=self.user)

    def test_requires_auth_unauthenticated_401(self) -> None:
        """인증 없이 confirm-code 요청 시 401"""
        self.client.force_authenticate(user=None)
        response = self.client.post(self.send_code_url, self.valid_phone_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_send_code_success_for_change_phone(self) -> None:
        self.send_code_success()

    def test_confirm_code_success_for_change_phone(self) -> None:
        self.confirm_code_success()

    def test_send_code_resend_cooldown_for_change_phone(self) -> None:
        self.send_code_resend_cooldown()

    def test_confirm_code_invalid_request_id_for_change_phone(self) -> None:
        self.confirm_code_invalid_request_id()

    def test_confirm_code_invalid_code_for_change_phone(self) -> None:
        self.confirm_code_invalid_code()

    def test_confirm_code_locked_for_change_phone(self) -> None:
        self.confirm_code_locked()
