from __future__ import annotations

from datetime import date
from typing import Any, ClassVar, Dict, Optional

from django.urls import reverse
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.test import APIClient, APITestCase
from unittest.mock import patch

from apps.users.models import User


class BasePhoneVerificationAPITest(APITestCase):
    """
    공통 데이터/헬퍼를 모아둔 베이스 클래스
    """

    # setUpTestData에서 채워질 클래스 속성
    user: ClassVar[User]

    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = User.objects.create(
            email="test@example.com",
            name="테스터",
            nickname="tester",
            phone_number="01012345678",
            gender="MALE",
            birthday=date(1990, 1, 1),
            is_active=True,
        )

    # 각 테스트 실행 직전 인스턴스 초기화
    def setUp(self) -> None:
        self.client: APIClient = APIClient()
        self.SEND_URL = reverse("users:phone_verifications:send_code")
        self.CONFIRM_URL = reverse("users:phone_verifications:confirm_code")
        # 공통 샘플 데이터
        self.valid_phone: str = "01012345678"
        self.invalid_phone: str = "010-abc"
        self.valid_code: str = "123456"
        self.invalid_code: str = "12ab"  # 숫자 6자 아님
        self.purpose_signup: str = "signup"
        self.purpose_change_phone: str = "change_phone"

        # mypy용 안전 바인딩
        self.current_user: User = type(self).user

    def post_json(self, url: str, payload: Dict[str, Any]) -> Response:
        return self.client.post(url, payload, format="json")

    def auth_as(self, user: Optional[User] = None) -> None:
        """
        DRF 인증 강제 적용. user가 None이면 공용 사용자로 인증.
        """
        self.client.force_authenticate(user or self.current_user)

    def build_send_payload(self, *, phone: Optional[str] = None, purpose: Optional[str] = None) -> Dict[str, Any]:
        return {
            "phone_number": phone or self.valid_phone,
            "purpose": purpose or self.purpose_signup,
        }

    def build_confirm_payload(
        self,
        *,
        phone: Optional[str] = None,
        purpose: Optional[str] = None,
        code: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "phone_number": phone or self.valid_phone,
            "purpose": purpose or self.purpose_signup,
            "code": code or self.valid_code,
        }



class PhoneVerificationAPITests(BasePhoneVerificationAPITest):

    @patch("apps.users.views.phone_verification_views.send_code")
    def test_send_code_success(self, mock_send_code: Any) -> None:
        """ 인증코드 전송 성공"""
        resp = self.post_json(self.SEND_URL, self.build_send_payload())
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        mock_send_code.assert_called_once_with(
            purpose=self.purpose_signup,
            phone_number=self.valid_phone,
        )

    def test_send_code_invalid_phone(self) -> None:
        """ 잘못된 번호 형식 -> 400"""
        resp = self.post_json(
            self.SEND_URL,
            self.build_send_payload(phone=self.invalid_phone),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("phone_number", resp.data)

    def test_send_code_missing_purpose(self) -> None:
        """ 필드 누락 -> 400"""
        payload = {"phone_number": self.valid_phone}  # purpose 누락
        resp = self.post_json(self.SEND_URL, payload)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("purpose", resp.data)

    def test_send_code_change_phone_requires_auth(self) -> None:
        """ change_phone 목적은 인증 필요 -> 401"""
        resp = self.post_json(
            self.SEND_URL,
            self.build_send_payload(purpose=self.purpose_change_phone),
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(resp.data.get("error"), "Authentication required")

    @patch("apps.users.views.phone_verification_views.send_code")
    def test_send_code_change_phone_authenticated_ok(self, mock_send_code: Any) -> None:
        """ change_phone 목적은 로그인 시 204"""
        self.auth_as(self.user)
        resp = self.post_json(
            self.SEND_URL,
            self.build_send_payload(purpose=self.purpose_change_phone),
        )
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        mock_send_code.assert_called_once_with(
            purpose=self.purpose_change_phone,
            phone_number=self.valid_phone,
        )


    @patch("apps.users.views.phone_verification_views.confirm_code")
    def test_confirm_code_success(self, mock_confirm_code: Any) -> None:
        """ 인증코드 확인 성공"""
        resp = self.post_json(self.CONFIRM_URL, self.build_confirm_payload())
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        mock_confirm_code.assert_called_once_with(
            purpose=self.purpose_signup,
            phone_number=self.valid_phone,
            code=self.valid_code,
            user_id=None,
        )

    def test_confirm_code_invalid_code_format(self) -> None:
        """ 코드 형식 오류(숫자 6자 아님) -> 400"""
        resp = self.post_json(
            self.CONFIRM_URL,
            self.build_confirm_payload(code=self.invalid_code),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("code", resp.data)

    @patch("apps.users.views.phone_verification_views.confirm_code")
    def test_confirm_code_authenticated_injects_user_id(self, mock_confirm_code: Any) -> None:
        """ 로그인 상태라면 confirm_code 호출 시 user_id 전달됨"""
        self.auth_as(self.user)
        resp = self.post_json(self.CONFIRM_URL, self.build_confirm_payload())
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        mock_confirm_code.assert_called_once_with(
            purpose=self.purpose_signup,
            phone_number=self.valid_phone,
            code=self.valid_code,
            user_id=self.user.id,
        )
