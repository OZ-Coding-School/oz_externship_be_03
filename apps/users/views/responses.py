from typing import Any, Mapping

from rest_framework import status
from rest_framework.response import Response


def ok(detail: str, data: Any | None = None, status_code: int = status.HTTP_200_OK) -> Response:
    """
    성공 응답 표준화
    - {"detail": "...", "data": {...}}
    - data가 None이면 detail만 내려감
    """
    payload: dict[str, Any] = {"detail": detail}
    if data is not None:
        payload["data"] = data
    return Response(payload, status=status_code)


def error(
    detail: str,
    *,
    status_code: int = status.HTTP_400_BAD_REQUEST,
    errors: Mapping[str, Any] | None = None,
) -> Response:
    """
    실패 응답 표준화
    - {"error": "에러 메시지"}
    회원 가입만 아래 형태
    - {
        "error": "입력값을 확인해주세요.",
        "errors": {
            "email": ["이미 사용 중인 이메일입니다."],
            "nickname": ["사용할 수 없는 닉네임입니다."],
            "phone_number": ["휴대폰 번호 형식이 올바르지 않습니다."]
        }
    }
    """
    payload: dict[str, Any] = {"error": detail}

    if errors is not None:
        payload["errors"] = errors

    return Response(payload, status=status_code)
