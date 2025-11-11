from __future__ import annotations

from typing import Any, Mapping, Type

from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.exceptions import ErrorDetail
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

# -------------------------------------------------
# 1) 공통 메시지
# -------------------------------------------------
COMMON_EXCEPTION_MESSAGES: dict[Type[BaseException], tuple[str, int]] = {
    Http404: ("요청한 리소스를 찾을 수 없습니다.", status.HTTP_404_NOT_FOUND),
    exceptions.PermissionDenied: ("접근 권한이 없습니다.", status.HTTP_403_FORBIDDEN),
    exceptions.AuthenticationFailed: ("잘못된 자격 증명입니다.", status.HTTP_401_UNAUTHORIZED),
    exceptions.NotAuthenticated: ("인증 정보가 제공되지 않았습니다.", status.HTTP_401_UNAUTHORIZED),
}


def match_common_exception(exc: Exception) -> Response | None:
    """404/401/403 공통 에러"""
    for exc_type, (msg, code) in COMMON_EXCEPTION_MESSAGES.items():
        if isinstance(exc, exc_type):
            return Response({"error": msg}, status=code)
    return None


# -------------------------------------------------
# 2) 전역 예외 핸들러
# -------------------------------------------------
def exception_handler(exc: Exception, context: dict[str, Any]) -> Response:
    """
    DRF 예외를 {"error": "메시지"} 형태로 통일
    """
    # 1) 공통 예외 먼저
    common = match_common_exception(exc)
    if common is not None:
        return common

    # 2) DRF 기본 처리
    response = drf_exception_handler(exc, context)
    if response is not None:
        data = response.data
        if isinstance(data, Mapping):
            return build_error_from_dict(data, response.status_code)
        return build_error_from_scalar(data, response.status_code)

    # 3) 500 에러
    return Response({"error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# -------------------------------------------------
# 3) 메시지 정규화
# -------------------------------------------------
def build_error_from_dict(data: Mapping[str, Any], status_code: int) -> Response:
    # 중복 'error:' 방지
    if "error" in data and isinstance(data["error"], (str, ErrorDetail)):
        return Response({"error": str(data["error"])}, status=status_code)

    if "detail" in data:
        return Response({"error": _first_text(data["detail"])}, status=status_code)

    # 그 외 필드 에러 합치기
    text = _build_error_message(data)
    return Response({"error": text}, status=status_code)


def build_error_from_scalar(data: Any, status_code: int) -> Response:
    text = _safe_str(data, default="요청이 올바르지 않습니다.")
    return Response({"error": text}, status=status_code)


def _build_error_message(data: Any) -> str:
    """
    DRF/Serializer 에러 payload를 문자열로 압축
    """
    # dict 종류
    if isinstance(data, Mapping):
        # 1) detail
        if "detail" in data:
            det = data["detail"]
            if isinstance(det, Mapping):
                text = _join_field_errors(det)
                if text:
                    return text
            return _first_text(det)

        # 2) non_field_errors
        if "non_field_errors" in data:
            return _first_text(data["non_field_errors"])

        text = _join_field_errors(data)
        return text or "요청이 올바르지 않습니다."

    # list/tuple 종류
    if isinstance(data, (list, tuple)):
        return _first_text(data)

    # 그 외
    return _safe_str(data, default="요청이 올바르지 않습니다.")


def _join_field_errors(field_errors: Mapping[str, Any]) -> str:
    """
    "field: msg1; field2: msg" 형태로 반환
    """
    parts: list[str] = []
    for field, errors in field_errors.items():
        if field in {"detail", "non_field_errors"}:
            continue
        msg = _first_text(errors)
        if msg:
            parts.append(f"{field}: {msg}")
    return "; ".join(parts)


def _first_text(value: Any) -> str:
    visited = 0
    current = value
    while visited < 100:
        visited += 1

        if isinstance(current, (list, tuple)):
            if not current:
                return "요청이 올바르지 않습니다."
            current = current[0]
            continue

        if isinstance(current, Mapping):
            if not current:
                return "요청이 올바르지 않습니다."
            for key in ("detail", "message", "non_field_errors"):
                if key in current:
                    current = current[key]
                    break
            else:
                # 아무 우선 키가 없으면 첫 value
                current = next(iter(current.values()))
            continue

        return _safe_str(current, default="요청이 올바르지 않습니다.")

    return "요청이 올바르지 않습니다."


def _safe_str(value: Any, default: str) -> str:
    return str(value) if value is not None and str(value).strip() else default
