from typing import Any, Dict, Optional

from rest_framework import status
from rest_framework.exceptions import APIException, _get_error_details


# Conflict 409 Error Custom
class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "중복된 데이터가 이미 존재합니다."
    default_code = "conflict"

    def __init__(self, detail: Optional[str | Dict[str, Any]] = None, code: Optional[str] = None) -> None:
        if detail is None:
            detail = self.default_detail
        if code is None:
            code = self.default_code

        self.detail = _get_error_details(detail, code)
