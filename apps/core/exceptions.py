from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Optional

from django.utils.timezone import localtime
from rest_framework import status
from rest_framework.exceptions import APIException


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
        super().__init__(detail=detail, code=code)


class WithdrawalBlocked(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_code = "user_withdrawal_pending"
    default_detail = "탈퇴 처리 중인 계정입니다."

    def __init__(self, *, blocked_until: date | datetime) -> None:
        if isinstance(blocked_until, datetime):
            blocked_date = localtime(blocked_until).date()
        else:
            blocked_date = blocked_until

        msg = f"탈퇴 처리 중인 계정입니다. {blocked_date:%Y년 %m월 %d일} 이후 가입이 가능합니다."
        payload: Dict[str, Any] = {
            "detail": msg,
            "data": {"blocked_until": blocked_date.isoformat()},
            "code": self.default_code,
        }
        super().__init__(detail=payload, code=self.default_code)
