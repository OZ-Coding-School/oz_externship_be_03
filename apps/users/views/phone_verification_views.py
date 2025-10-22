from __future__ import annotations

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.serializers.phone_verification_serializers import (
    ConfirmCodeResponseSerializer,
    ConfirmCodeSerializer,
    SendCodeResponseSerializer,
    SendCodeSerializer,
)
from apps.users.services.phone_verification_services import confirm_code, send_code


@extend_schema(
    tags=["Users"],
    summary="휴대폰 인증코드 전송",
    description="Twilio Verify를 통해 휴대폰으로 인증코드를 전송합니다.",
    request=SendCodeSerializer,
    responses=inline_serializer(
        name="PhoneVerificationSendCodeResponse",
        fields={
            "detail": serializers.CharField(),
            "data": SendCodeResponseSerializer(),
        },
    ),
)
class PhoneSendCodeView(APIView):
    """
    목적(purpose)에 따라 권한 정책:
    - signup / find_email
    - change_phone : 로그인 필요
    """

    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = SendCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        purpose = serializer.validated_data["purpose"]
        phone_number = serializer.validated_data["phone_number"]

        # 권한 분기
        if purpose == "change_phone" and not request.user.is_authenticated:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        result = send_code(
            purpose=purpose,
            phone_number=phone_number,
        )
        # 서비스가 에러일 때 Response 그대로 반환
        if isinstance(result, Response):
            return result

        resp_serializer = SendCodeResponseSerializer(result)

        return Response(
            {"detail": "인증코드를 발송했습니다.", "data": resp_serializer.data},
            status=status.HTTP_200_OK,
        )


@extend_schema(
    tags=["Users"],
    summary="휴대폰 인증코드 확인",
    description="사용자가 받은 인증코드를 검증합니다. 성공 시 이후 단계에서 소비할 원타임 키가 저장됩니다.",
    request=ConfirmCodeSerializer,
    responses=inline_serializer(
        name="PhoneVerificationSendCodeResponse",
        fields={
            "detail": serializers.CharField(),
            "data": ConfirmCodeResponseSerializer(),
        },
    ),
)
class PhoneConfirmCodeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        req_serializer = ConfirmCodeSerializer(data=request.data)
        req_serializer.is_valid(raise_exception=True)
        purpose = req_serializer.validated_data["purpose"]
        phone_number = req_serializer.validated_data["phone_number"]
        code = req_serializer.validated_data["code"]
        request_id = req_serializer.validated_data["request_id"]

        result = confirm_code(purpose=purpose, phone_number=phone_number, code=code, request_id=request_id)
        # 서비스가 에러일 때 Response 그대로 반환
        if isinstance(result, Response):
            return result

        resp_serializer = ConfirmCodeResponseSerializer(result)

        return Response(
            {"detail": "인증이 완료되었습니다.", "data": resp_serializer.data},
            status=status.HTTP_200_OK,
        )
