from typing import Dict, Optional, cast

from rest_framework import status
from rest_framework.exceptions import APIException, ErrorDetail


class RecruitmentServiceException(APIException):
    """
    리크루트먼트 서비스 전용 예외 기본 클래스
    """

    status_code: int = status.HTTP_400_BAD_REQUEST
    default_detail: str = "잘못된 요청입니다."
    default_code: str = "invalid_request"

    def __init__(
        self,
        error_message: Optional[str] = None,
        detail_code: Optional[str] = None,
        status_code: Optional[int] = None,
    ) -> None:
        if status_code is not None:
            self.status_code = int(status_code)

        error_dict: Dict[str, ErrorDetail] = {
            "error": ErrorDetail(error_message or self.default_detail),
            "detail": ErrorDetail(detail_code or self.default_code),
        }

        self.detail = error_dict  # type: ignore[assignment]
