from __future__ import annotations

from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.core.utils.isolated_cache_testcase import IsolatedRedisTestClient
from apps.users.services.phone_verification_services import (
    _global_lock_key,
    _lock_key,
    _normalize_kr_phone,
    _pending_key,
)

User = get_user_model()


# =========================
# [PUBLIC] signup / find_email
# =========================
class PublicPhoneVerificationViewTests(IsolatedRedisTestClient):
    def setUp(self) -> None:
        super().setUp()
        self.send_code_url = reverse("users:send_code")
        self.confirm_code_url = reverse("users:confirm_code")
        self.valid_phone_data = {
            "phone_number": "01012345678",
            "purpose": "signup",
        }
        self.valid_confirm_data = {
            "phone_number": "01012345678",
            "purpose": "signup",
            "request_id": "SID12345",
            "code": "123456",
        }

    # --- [PUBLIC] send-code ---

    @patch("apps.users.services.phone_verification_services._twilio")
    def test_public_send_code_success(self, mock_twilio: Mock) -> None:
        """[PUBLIC] 휴대폰 인증코드 전송 성공"""
        mock_twilio.verify.v2.services.return_value.verifications.create.return_value.sid = "SID12345"

        response = self.client.post(self.send_code_url, self.valid_phone_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["detail"], "인증코드를 발송했습니다.")
        self.assertIn("data", data)
        self.assertEqual(data["data"]["request_id"], "SID12345")
        self.assertIsInstance(data["data"]["expires_in"], int)
        self.assertIsInstance(data["data"]["cooldown"], int)
        self.assertIsInstance(data["data"]["max_attempts"], int)

    @patch("apps.users.services.phone_verification_services._twilio")
    def test_public_send_code_resend_cooldown(self, mock_twilio: Mock) -> None:
        """[PUBLIC] 재전송 쿨다운 중 요청 시 429"""
        mock_twilio.verify.v2.services.return_value.verifications.create.return_value.sid = "SID12345"

        self.client.post(self.send_code_url, self.valid_phone_data, format="json")
        response = self.client.post(self.send_code_url, self.valid_phone_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn("error", response.json())

    # --- [PUBLIC] confirm-code ---

    @patch("apps.users.services.phone_verification_services.issue_verify_token", return_value="mocked-token")
    @patch("apps.users.services.phone_verification_services._twilio")
    def test_public_confirm_code_success(self, mock_twilio: Mock, mock_issue_token: Mock) -> None:
        """[PUBLIC] 휴대폰 인증코드 검증 성공"""
        mock_twilio.verify.v2.services.return_value.verification_checks.create.return_value.status = "approved"

        key = _pending_key(
            subject=self.valid_confirm_data["phone_number"],
            purpose=self.valid_confirm_data["purpose"],
            sid=self.valid_confirm_data["request_id"],
        )
        cache.set(key, "+821012345678", timeout=600)

        response = self.client.post(self.confirm_code_url, self.valid_confirm_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["detail"], "인증이 완료되었습니다.")
        self.assertEqual(data["data"]["verify_token"], "mocked-token")
        self.assertIsInstance(data["data"]["expires_in"], int)

    @patch("apps.users.services.phone_verification_services._twilio")
    def test_public_confirm_code_invalid_request_id(self, mock_twilio: Mock) -> None:
        """[PUBLIC] 잘못된 request_id로 요청 시 404"""
        mock_twilio.verify.v2.services.return_value.verification_checks.create.return_value.status = "approved"

        response = self.client.post(self.confirm_code_url, self.valid_confirm_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.json())

    @patch("apps.users.services.phone_verification_services._twilio")
    def test_public_confirm_code_invalid_code(self, mock_twilio: Mock) -> None:
        """[PUBLIC] 인증코드 불일치 시 400"""
        mock_twilio.verify.v2.services.return_value.verification_checks.create.return_value.status = "pending"

        key = _pending_key(
            subject=self.valid_confirm_data["phone_number"],
            purpose=self.valid_confirm_data["purpose"],
            sid=self.valid_confirm_data["request_id"],
        )
        cache.set(key, "+821012345678", timeout=600)

        response = self.client.post(self.confirm_code_url, self.valid_confirm_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.json())

    @patch("apps.users.services.phone_verification_services._twilio")
    def test_public_confirm_code_locked_returns_429(self, mock_twilio: Mock) -> None:
        """[PUBLIC] 락이 걸린 번호/목적에 대해 429"""
        mock_twilio.verify.v2.services.return_value.verification_checks.create.return_value.status = "approved"

        to = _normalize_kr_phone(self.valid_confirm_data["phone_number"])
        cache.set(_global_lock_key(to), "1", timeout=60)
        cache.set(_lock_key(to, self.valid_confirm_data["purpose"]), "1", timeout=60)

        response = self.client.post(self.confirm_code_url, self.valid_confirm_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn("error", response.json())


# =========================
# [AUTH] change_phone
# =========================
class ChangePhoneVerificationViewTests(IsolatedRedisTestClient):
    def setUp(self) -> None:
        super().setUp()
        self.send_code_url = reverse("users:change_phone_send_code")
        self.confirm_code_url = reverse("users:change_phone_confirm_code")

        # change_phone 엔드포인트는 purpose를 받지 않음 (서버가 고정)
        self.valid_phone_data = {
            "phone_number": "01099998888",
        }
        self.valid_confirm_data = {
            "phone_number": "01099998888",
            "request_id": "SID77777",
            "code": "654321",
        }

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

    def tearDown(self) -> None:
        cache.clear()

    # --- [AUTH] send-code ---

    def test_change_phone_send_code_requires_auth(self) -> None:
        """[AUTH] 인증 없이 요청 시 401"""
        response = self.client.post(self.send_code_url, self.valid_phone_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("apps.users.services.phone_verification_services._twilio")
    def test_change_phone_send_code_success(self, mock_twilio: Mock) -> None:
        """[AUTH] 휴대폰 변경 - 인증코드 전송 성공"""
        self.client.force_authenticate(user=self.user)
        mock_twilio.verify.v2.services.return_value.verifications.create.return_value.sid = "SID77777"

        response = self.client.post(self.send_code_url, self.valid_phone_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["detail"], "인증코드를 발송했습니다.")
        self.assertIn("data", data)
        self.assertEqual(data["data"]["request_id"], "SID77777")
        self.assertIsInstance(data["data"]["expires_in"], int)
        self.assertIsInstance(data["data"]["cooldown"], int)
        self.assertIsInstance(data["data"]["max_attempts"], int)

    @patch("apps.users.services.phone_verification_services._twilio")
    def test_change_phone_send_code_resend_cooldown(self, mock_twilio: Mock) -> None:
        """[AUTH] 재전송 쿨다운 중 요청 시 429"""
        self.client.force_authenticate(user=self.user)
        mock_twilio.verify.v2.services.return_value.verifications.create.return_value.sid = "SID77777"

        self.client.post(self.send_code_url, self.valid_phone_data, format="json")
        response = self.client.post(self.send_code_url, self.valid_phone_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn("error", response.json())

    # --- [AUTH] confirm-code ---

    def test_change_phone_confirm_code_requires_auth(self) -> None:
        """[AUTH] 인증 없이 confirm-code 요청 시 401"""
        response = self.client.post(self.confirm_code_url, self.valid_confirm_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("apps.users.services.phone_verification_services.issue_verify_token", return_value="mocked-token")
    @patch("apps.users.services.phone_verification_services._twilio")
    def test_change_phone_confirm_code_success(self, mock_twilio: Mock, mock_issue: Mock) -> None:
        """[AUTH] 휴대폰 변경 - 인증코드 검증 성공"""
        self.client.force_authenticate(user=self.user)
        mock_twilio.verify.v2.services.return_value.verification_checks.create.return_value.status = "approved"

        # change_phone는 purpose가 서버 고정이므로 pending 키도 change_phone로 저장
        key = _pending_key(
            subject=self.valid_confirm_data["phone_number"],
            purpose="change_phone",
            sid=self.valid_confirm_data["request_id"],
        )
        cache.set(key, "+821099998888", timeout=600)

        response = self.client.post(self.confirm_code_url, self.valid_confirm_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["detail"], "인증이 완료되었습니다.")
        self.assertEqual(data["data"]["verify_token"], "mocked-token")
        self.assertIsInstance(data["data"]["expires_in"], int)

    @patch("apps.users.services.phone_verification_services._twilio")
    def test_change_phone_confirm_code_invalid_request_id(self, mock_twilio: Mock) -> None:
        """[AUTH] 잘못된 request_id로 요청 시 404"""
        self.client.force_authenticate(user=self.user)
        mock_twilio.verify.v2.services.return_value.verification_checks.create.return_value.status = "approved"

        response = self.client.post(self.confirm_code_url, self.valid_confirm_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.json())

    @patch("apps.users.services.phone_verification_services._twilio")
    def test_change_phone_confirm_code_invalid_code(self, mock_twilio: Mock) -> None:
        """[AUTH] 인증코드 불일치 시 400"""
        self.client.force_authenticate(user=self.user)
        mock_twilio.verify.v2.services.return_value.verification_checks.create.return_value.status = "pending"

        key = _pending_key(
            subject=self.valid_confirm_data["phone_number"],
            purpose="change_phone",
            sid=self.valid_confirm_data["request_id"],
        )
        cache.set(key, "+821099998888", timeout=600)

        response = self.client.post(self.confirm_code_url, self.valid_confirm_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.json())

    @patch("apps.users.services.phone_verification_services._twilio")
    def test_change_phone_confirm_code_locked_returns_429(self, mock_twilio: Mock) -> None:
        """[AUTH] 락이 걸린 번호/목적(change_phone)에 대해 429"""
        self.client.force_authenticate(user=self.user)
        mock_twilio.verify.v2.services.return_value.verification_checks.create.return_value.status = "approved"

        to = _normalize_kr_phone(self.valid_confirm_data["phone_number"])
        cache.set(_global_lock_key(to), "1", timeout=60)
        cache.set(_lock_key(to, "change_phone"), "1", timeout=60)

        response = self.client.post(self.confirm_code_url, self.valid_confirm_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn("error", response.json())
