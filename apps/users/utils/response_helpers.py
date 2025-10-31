from typing import Any

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
