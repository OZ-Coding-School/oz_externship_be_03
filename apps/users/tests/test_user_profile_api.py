from __future__ import annotations

import random
from datetime import date
from typing import TYPE_CHECKING, Any, ClassVar, Final
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.http import Http404
from django.test import Client, TestCase
from django.urls import reverse
from rest_framework import exceptions, status
from rest_framework.exceptions import NotAuthenticated
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.utils.exception_handler import (
    _build_error_message,
    _first_text,
    _safe_str,
    exception_handler,
)

if TYPE_CHECKING:
    from apps.users.models.user import User as UserType

User = get_user_model()


# ==============================
# 유저 프로필 조회 테스트
# ==============================
class MeAPITest(APITestCase):
    def setUp(self) -> None:
        """
        테스트용 유저 생성 및 JWT 인증 설정
        """
        # 테스트용 유저 생성
        self.user = User.objects.create_user(
            email="user@example.com",
            password="password123",
            nickname="ozdev",
            name="홍길동",
            phone_number="01012345678",
            birthday="1998-01-23",
            gender="M",
            is_active=True,
        )

        # JWT 토큰 발급
        refresh = RefreshToken.for_user(self.user)
        self.access_token = str(refresh.access_token)

        # 인증 헤더 설정
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

    def test_me_success(self) -> None:
        """
        로그인한 사용자가 /api/v1/me 조회 성공
        """
        url = reverse("users:me")
        response = self.client.get(url)

        # 검증
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["email"], self.user.email)
        self.assertEqual(response.data["nickname"], self.user.nickname)
        self.assertEqual(response.data["name"], self.user.name)
        self.assertIn("profile_img_url", response.data)  # 필드 존재 확인
        self.assertIn("created_at", response.data)

    def test_me_unauthorized(self) -> None:
        """
        인증되지 않은 요청은 401 반환
        """
        self.client.credentials()  # 인증 헤더 제거
        url = reverse("users:me")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["detail"], str(NotAuthenticated.default_detail))


# ==============================
# 중복 닉네임 검증 테스트
# ==============================
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
) -> UserType:
    """유저 생성"""
    suffix = uuid4().hex[:6]
    if email is None:
        email = f"user{suffix}@example.com"
    if nickname is None:
        nickname = f"nick{suffix}"
    if phone_number is None:
        phone_number = f"010-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}"

    user = User.objects.create_user(
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


class UserDupNicknameViewTests(TestCase):
    existing: ClassVar[UserType]
    url: ClassVar[str]

    @classmethod
    def setUpTestData(cls) -> None:
        cls.existing = make_user(nickname="Winter")
        cls.url = reverse("users:dup_nickname")

    def setUp(self) -> None:
        self.client = Client()

    def test_missing_nickname_returns_400(self) -> None:
        # nickname 미제공
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.json())

        # 공백만 전달
        resp2 = self.client.get(self.url, {"nickname": "   "})
        self.assertEqual(resp2.status_code, 400)
        self.assertIn("error", resp2.json())

    def test_default_case_insensitive_duplicates(self) -> None:
        # 기본값: 대소문자 구분 안함 → Winter vs winter => 중복
        resp = self.client.get(self.url, {"nickname": "winter"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("detail", body)
        self.assertIn("data", body)
        self.assertEqual(body["data"]["nickname"], "winter")
        self.assertFalse(body["data"]["available"])  # 중복

    def test_not_duplicate_when_not_exists(self) -> None:
        resp = self.client.get(self.url, {"nickname": "BrandNewNick"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["data"]["available"])  # 사용 가능
        self.assertEqual(body["data"]["nickname"], "BrandNewNick")

    def test_case_sensitive_false_flag(self) -> None:
        # case_insensitive=false → 대소문자 지켜서 중복 확인
        resp = self.client.get(self.url, {"nickname": "winter", "case_insensitive": "false"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["data"]["available"])

        resp2 = self.client.get(self.url, {"nickname": "Winter", "case_insensitive": "false"})
        self.assertEqual(resp2.status_code, 200)
        self.assertFalse(resp2.json()["data"]["available"])

    def test_trims_spaces(self) -> None:
        # 앞뒤 공백 제거되어 Winter 비교 → 중복
        resp = self.client.get(self.url, {"nickname": "  Winter  "})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["data"]["available"])

    def test_truthy_values_for_case_insensitive(self) -> None:
        # true/1만 true로 처리 ({"1","true"}만 true)
        # "true" → 중복
        resp_true = self.client.get(self.url, {"nickname": "winter", "case_insensitive": "true"})
        self.assertFalse(resp_true.json()["data"]["available"])

        # "1" → 중복
        resp_one = self.client.get(self.url, {"nickname": "winter", "case_insensitive": "1"})
        self.assertFalse(resp_one.json()["data"]["available"])

        # "0" → false 처리 → 대소문 구분
        resp_yes = self.client.get(self.url, {"nickname": "winter", "case_insensitive": "0"})
        self.assertTrue(resp_yes.json()["data"]["available"])


# ==============================
# exeption handler 테스트
# ==============================
class ExceptionHandlerTests(TestCase):
    def test_http404_returns_404_error_message(self) -> None:
        exc = Http404()
        response = exception_handler(exc, {})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"], "요청한 리소스를 찾을 수 없습니다.")

    def test_permission_denied_returns_403(self) -> None:
        exc = exceptions.PermissionDenied()
        response = exception_handler(exc, {})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["error"], "접근 권한이 없습니다.")

    def test_authentication_failed_returns_401(self) -> None:
        exc = exceptions.AuthenticationFailed()
        response = exception_handler(exc, {})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["error"], "잘못된 자격 증명입니다.")

    def test_not_authenticated_returns_401(self) -> None:
        exc = exceptions.NotAuthenticated()
        response = exception_handler(exc, {})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["error"], "인증 정보가 제공되지 않았습니다.")

    def test_unexpected_exception_returns_500(self) -> None:
        exc = ValueError("예상치 못한 오류")
        response = exception_handler(exc, {})
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("예상치 못한 오류", response.data["error"])

    # ======================
    # _build_error_message 분기 테스트
    # ======================
    def test_build_error_message_with_detail_mapping(self) -> None:
        data = {"detail": {"field1": ["error1"], "field2": ["error2"]}}
        self.assertIn("field1: error1", _build_error_message(data))

    def test_build_error_message_with_non_field_errors(self) -> None:
        data = {"non_field_errors": ["global error"]}
        self.assertEqual(_build_error_message(data), "global error")

    def test_build_error_message_with_list(self) -> None:
        data = ["simple error"]
        self.assertEqual(_build_error_message(data), "simple error")

    def test_build_error_message_with_plain_string(self) -> None:
        data = "plain error"
        self.assertEqual(_build_error_message(data), "plain error")

    def test_build_error_message_with_empty_mapping(self) -> None:
        data: dict[str, Any] = {}
        self.assertEqual(_build_error_message(data), "요청이 올바르지 않습니다.")

    # ======================
    # _first_text 커버리지 테스트
    # ======================
    def test_first_text_with_nested_list_and_dict(self) -> None:
        value = [{"detail": [{"message": "deep error"}]}]
        self.assertEqual(_first_text(value), "deep error")

    def test_first_text_with_empty_list(self) -> None:
        self.assertEqual(_first_text([]), "요청이 올바르지 않습니다.")

    def test_first_text_with_empty_dict(self) -> None:
        self.assertEqual(_first_text({}), "요청이 올바르지 않습니다.")

    def test_first_text_with_unexpected_type(self) -> None:
        self.assertEqual(_first_text(1234), "1234")

    # ======================
    # _safe_str 커버리지 테스트
    # ======================
    def test_safe_str_with_none_and_blank(self) -> None:
        self.assertEqual(_safe_str(None, "DEFAULT"), "DEFAULT")
        self.assertEqual(_safe_str("   ", "DEFAULT"), "DEFAULT")

    def test_safe_str_with_normal_value(self) -> None:
        self.assertEqual(_safe_str("Hello", "DEFAULT"), "Hello")
