from __future__ import annotations

from typing import Any

from django.http import Http404
from django.test import TestCase
from rest_framework import status
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied,
)

from apps.core.utils.exception_handler import (
    _build_error_message,
    _first_text,
    _safe_str,
    exception_handler,
)


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
        exc = PermissionDenied()
        response = exception_handler(exc, {})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["error"], "접근 권한이 없습니다.")

    def test_authentication_failed_returns_401(self) -> None:
        exc = AuthenticationFailed()
        response = exception_handler(exc, {})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["error"], "잘못된 자격 증명입니다.")

    def test_not_authenticated_returns_401(self) -> None:
        exc = NotAuthenticated()
        response = exception_handler(exc, {})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["error"], "인증 정보가 제공되지 않았습니다.")

    def test_unexpected_exception_returns_500(self) -> None:
        exc = ValueError("예상치 못한 오류")
        response = exception_handler(exc, {})
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("예상치 못한 오류", response.data["error"])

    # ======================
    # _build_error_message
    # ======================
    def test_build_error_message_with_detail_mapping(self) -> None:
        data = {"detail": {"field1": ["error1"], "field2": ["error2"]}}
        self.assertIn("field1: error1", _build_error_message(data))
        self.assertIn("field2: error2", _build_error_message(data))

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
    # _first_text
    # ======================
    def test_first_text_with_nested_list_and_dict(self) -> None:
        value = [{"detail": [{"message": "deep error"}]}]
        self.assertEqual(_first_text(value), "deep error")

    def test_first_text_with_empty_dict(self) -> None:
        self.assertEqual(_first_text({}), "요청이 올바르지 않습니다.")

    def test_first_text_with_unexpected_type(self) -> None:
        self.assertEqual(_first_text(1234), "1234")

    # ======================
    # _safe_str
    # ======================
    def test_safe_str_with_none_and_blank(self) -> None:
        self.assertEqual(_safe_str(None, "DEFAULT"), "DEFAULT")
        self.assertEqual(_safe_str("   ", "DEFAULT"), "DEFAULT")

    def test_safe_str_with_normal_value(self) -> None:
        self.assertEqual(_safe_str("Hello", "DEFAULT"), "Hello")

    # =======================
    # 예외 처리
    # =======================
    def test_invalid_authentication_failed(self) -> None:
        exc = AuthenticationFailed("로그인 실패")
        response = exception_handler(exc, {})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["error"], "잘못된 자격 증명입니다.")

    # ==============================
    # custom_messages
    # ==============================
    def test_http404_exception_handler(self) -> None:
        exc = Http404("리소스를 찾을 수 없습니다.")
        response = exception_handler(exc, {})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"], "요청한 리소스를 찾을 수 없습니다.")

    def test_permission_denied_exception_handler(self) -> None:
        exc = PermissionDenied("접근 권한이 없습니다.")
        response = exception_handler(exc, {})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["error"], "접근 권한이 없습니다.")

    def test_authentication_failed_exception_handler(self) -> None:
        exc = AuthenticationFailed("잘못된 자격 증명입니다.")
        response = exception_handler(exc, {})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["error"], "잘못된 자격 증명입니다.")

    def test_not_authenticated_exception_handler(self) -> None:
        exc = NotAuthenticated("인증 정보가 제공되지 않았습니다.")
        response = exception_handler(exc, {})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["error"], "인증 정보가 제공되지 않았습니다.")

    # ==============================
    # _build_error_message에서 "detail" 처리
    # ==============================
    def test_build_error_message_with_detail(self) -> None:
        data = {"detail": {"field1": ["error1"], "field2": ["error2"]}}
        message = _build_error_message(data)
        self.assertIn("field1: error1", message)
        self.assertIn("field2: error2", message)

    def test_build_error_message_with_empty_detail(self) -> None:
        data: dict[str, Any] = {"detail": {}}
        message = _build_error_message(data)
        self.assertEqual(message, "요청이 올바르지 않습니다.")

    # ==============================
    # _first_text 커버리지
    # ==============================
    def test_first_text_with_list(self) -> None:
        value = ["error1", "error2"]
        self.assertEqual(_first_text(value), "error1")

    def test_first_text_with_empty_list(self) -> None:
        self.assertEqual(_first_text([]), "요청이 올바르지 않습니다.")

    def test_first_text_with_dict(self) -> None:
        value = {"detail": "message"}
        self.assertEqual(_first_text(value), "message")

    def test_first_text_with_invalid_type(self) -> None:
        self.assertEqual(_first_text(1234), "1234")

    # ==============================
    # _safe_str 커버리지
    # ==============================
    def test_safe_str_with_none(self) -> None:
        self.assertEqual(_safe_str(None, "기본값"), "기본값")

    def test_safe_str_with_empty_string(self) -> None:
        self.assertEqual(_safe_str("   ", "기본값"), "기본값")

    def test_safe_str_with_non_empty_string(self) -> None:
        self.assertEqual(_safe_str("Valid string", "기본값"), "Valid string")

    def test_safe_str_with_default_for_none(self) -> None:
        self.assertEqual(_safe_str(None, "DEFAULT"), "DEFAULT")

    def test_safe_str_with_default_for_empty(self) -> None:
        self.assertEqual(_safe_str(" ", "DEFAULT"), "DEFAULT")
