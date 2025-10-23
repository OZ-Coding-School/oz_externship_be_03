from __future__ import annotations

from typing import Any, Dict, Union, cast

from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
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


@extend_schema_view(
    post=extend_schema(
        tags=["Users"],
        summary="이메일 인증코드 발송",
        description="요청한 이메일과 용도(purpose)에 대해 인증코드를 발송함.",
        request=EmailVerificationRequestSerializer,
        responses={
            200: EmailVerificationSendCodeResponseSerializer,
            400: OpenApiResponse(description="요청 본문 검증 실패"),
            429: OpenApiResponse(description="재전송 쿨다운/시도 제한 등으로 인한 거절"),
            500: OpenApiResponse(description="서버 오류"),
        },
    )
)
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


@extend_schema_view(
    post=extend_schema(
        tags=["Users"],
        summary="이메일 인증코드 확인",
        description="인증코드와 request_id를 검증하여 인증을 완료함.",
        request=EmailVerifyCodeSerializer,
        responses={
            200: EmailVerifyCodeResponseSerializer,
            400: OpenApiResponse(description="요청 본문 검증 실패 또는 잘못된 코드"),
            404: OpenApiResponse(description="요청 이력(request_id) 없음 또는 만료"),
            409: OpenApiResponse(description="이미 인증 완료된 요청"),
            410: OpenApiResponse(description="인증코드 만료"),
            500: OpenApiResponse(description="서버 오류"),
        },
    )
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
