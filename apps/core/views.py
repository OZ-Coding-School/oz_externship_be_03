from __future__ import annotations

from typing import Any, Dict

from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.utils.exception_handler import exception_handler as _exc


class ExceptionHandledAPIView(APIView):
    """예외가 항상 {"error": "..."} 포맷으로 반환"""

    def handle_exception(self, exc: Exception) -> Response:
        context: Dict[str, Any] = {"request": getattr(self, "request", None), "view": self}
        return _exc(exc, context)
