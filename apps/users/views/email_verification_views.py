from __future__ import annotations

from typing import Any, Dict, Union, cast

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.enums import EmailVerificationPurpose
from apps.users.serializers.email_verification_serializers import (
    EmailVerificationRequestSerializer,
    EmailVerificationSendCodeResponseSerializer,
    EmailVerifyCodeResponseSerializer,
    EmailVerifyCodeSerializer,
)
from apps.users.services import email_verification_services as svc


class EmailSendCodeView(APIView):
    """
    POST /api/users/email/send-code
    """

    def post(self, request: Request) -> Response:
        serializer = EmailVerificationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email: str = cast(str, serializer.validated_data["email"])
        purpose: EmailVerificationPurpose = cast(EmailVerificationPurpose, serializer.validated_data["purpose"])

        result: Union[Response, Dict[str, Any]] = svc.email_send_code(purpose=purpose, email=email)
        if isinstance(result, Response):
            return result

        meta = EmailVerificationSendCodeResponseSerializer(result).data
        return Response(
            {"detail": "인증코드를 발송했습니다.", "data": meta},
            status=status.HTTP_200_OK,
        )


class EmailConfirmCodeView(APIView):
    """
    POST /api/users/email/confirm-code
    """

    def post(self, request: Request) -> Response:
        serializer = EmailVerifyCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email: str = cast(str, serializer.validated_data["email"])
        purpose: EmailVerificationPurpose = cast(EmailVerificationPurpose, serializer.validated_data["purpose"])
        verification_code: str = cast(str, serializer.validated_data["verification_code"])
        request_id: str = cast(str, serializer.validated_data["request_id"])

        result: Union[Response, Dict[str, Any]] = svc.email_confirm_code(
            purpose=purpose,
            email=email,
            verification_code=verification_code,
            request_id=request_id,
        )
        if isinstance(result, Response):
            return result

        meta = EmailVerifyCodeResponseSerializer(result).data
        return Response(
            {"detail": "인증이 완료되었습니다.", "data": meta},
            status=status.HTTP_200_OK,
        )
