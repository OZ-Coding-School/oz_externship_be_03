from __future__ import annotations

from typing import Dict

from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response

from apps.core.utils.exception_handler import (
    _first_text,
    build_error_from_dict,
    build_error_from_scalar,
    match_common_exception,
)
from apps.core.views import ExceptionHandledAPIView

STATUS_MESSAGES: Dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: "입력값을 확인해주세요.",
    status.HTTP_409_CONFLICT: "이미 사용 중인 입력값이 있습니다.",
    status.HTTP_422_UNPROCESSABLE_ENTITY: "요청을 처리할 수 없는 상태입니다.",
}


class SignupExceptionHandledAPIView(ExceptionHandledAPIView):
    """
    회원가입/인증 전용 예외 핸들러
    """

    def handle_exception(self, exc: Exception) -> Response:
        # 공통 예외 처리 적용
        response = super().handle_exception(exc)
        if response is not None:
            return response

        # Http404, 인증/권한 관련 공통 예외 → core 처리
        common_response = match_common_exception(exc)
        if common_response is not None:
            return common_response

        # 회원가입/인증 관련 예외 처리
        if isinstance(exc, (ValidationError, APIException)):
            status_code = getattr(exc, "status_code", status.HTTP_400_BAD_REQUEST)

            if status_code >= 500:
                return super().handle_exception(exc)

            detail = getattr(exc, "detail", None)
            if isinstance(detail, dict):
                return build_error_from_dict(detail, status_code)

            return build_error_from_scalar(detail, status_code)

        return super().handle_exception(exc)


class LoginExceptionHandledAPIView(ExceptionHandledAPIView):
    """
    로그인 전용 예외 핸들러
    - 403인 경우 detail+data 패턴이면 {"error", "data", "code"}로 리턴
    - 그 외는 공통 규칙 사용
    """

    def handle_exception(self, exc: Exception) -> Response:
        # 1) 403을 먼저 처리
        status_code = getattr(exc, "status_code", None)
        if status_code == status.HTTP_403_FORBIDDEN:
            detail = getattr(exc, "detail", None)

            if isinstance(detail, dict):
                # {"detail": ..., "data": ...}
                if "detail" in detail and "data" in detail:
                    body = {
                        "error": _first_text(detail["detail"]),
                        "data": detail.get("data"),
                    }
                    return Response(body, status=status.HTTP_403_FORBIDDEN)

                return build_error_from_dict(detail, status.HTTP_403_FORBIDDEN)

            return build_error_from_scalar(detail, status.HTTP_403_FORBIDDEN)

        # 2) 403 외 상태는 기존 글로벌 핸들러(super)로 처리
        return super().handle_exception(exc)
