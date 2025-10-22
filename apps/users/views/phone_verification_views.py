from __future__ import annotations

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.enums import PhoneVerificationPurpose
from apps.users.serializers.phone_verification_serializers import (
    ChangePhoneConfirmCodeSerializer,
    ChangePhoneSendCodeSerializer,
    ConfirmCodeResponseSerializer,
    ConfirmCodeSerializer,
    SendCodeResponseSerializer,
    SendCodeSerializer,
)
from apps.users.services.phone_verification_services import confirm_code, send_code

# -------------------------------
# 공개용 (signup / find_email)
# -------------------------------


@extend_schema(
    tags=["Users"],
    summary="휴대폰 인증코드 전송 - 회원가입, 이메일 찾기",
    description="회원가입, 이메일 찾기 목적으로 Twilio Verify를 통해 휴대폰으로 인증코드를 전송합니다. 로그인이 필요하지 않습니다.",
    request=SendCodeSerializer,
    responses=inline_serializer(
        name="PhoneVerificationSendCodeResponse",
        fields={
            "detail": serializers.CharField(),
            "data": SendCodeResponseSerializer(),
        },
    ),
)
class PublicPhoneSendCodeView(APIView):
    """
    purpose : signup / find_email
    """

    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = SendCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        purpose = serializer.validated_data["purpose"]
        phone_number = serializer.validated_data["phone_number"]

        if purpose not in {PhoneVerificationPurpose.SIGNUP, PhoneVerificationPurpose.FIND_EMAIL}:
            return Response({"error": "요청한 목적이 올바르지 않습니다."}, status=status.HTTP_400_BAD_REQUEST)

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
    summary="휴대폰 인증코드 확인 - 회원가입, 이메일 찾기",
    description="회원가입, 이메일 찾기 목적으로 Twilio Verify를 통해 휴대폰으로 인증코드를 확인합니다. 로그인이 필요하지 않습니다.",
    request=ConfirmCodeSerializer,
    responses=inline_serializer(
        name="PhoneVerificationSendCodeResponse",
        fields={
            "detail": serializers.CharField(),
            "data": ConfirmCodeResponseSerializer(),
        },
    ),
)
class PublicPhoneConfirmCodeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        req_serializer = ConfirmCodeSerializer(data=request.data)
        req_serializer.is_valid(raise_exception=True)
        purpose = req_serializer.validated_data["purpose"]
        phone_number = req_serializer.validated_data["phone_number"]
        code = req_serializer.validated_data["code"]
        request_id = req_serializer.validated_data["request_id"]

        if purpose not in {PhoneVerificationPurpose.SIGNUP, PhoneVerificationPurpose.FIND_EMAIL}:
            return Response({"error": "요청한 목적이 올바르지 않습니다."}, status=status.HTTP_400_BAD_REQUEST)

        result = confirm_code(purpose=purpose, phone_number=phone_number, code=code, request_id=request_id)
        # 서비스가 에러일 때 Response 그대로 반환
        if isinstance(result, Response):
            return result

        resp_serializer = ConfirmCodeResponseSerializer(result)

        return Response(
            {"detail": "인증이 완료되었습니다.", "data": resp_serializer.data},
            status=status.HTTP_200_OK,
        )


# -------------------------------
# 인증용 (change_phone) — 서버가 purpose 고정
# -------------------------------


@extend_schema(
    tags=["Users"],
    summary="휴대폰 인증코드 전송 - 휴대폰 번호 변경",
    description="휴대폰 번호 변경 목적으로 Twilio Verify를 통해 휴대폰으로 인증코드를 전송합니다. 로그인이 필요합니다.",
    request=ChangePhoneSendCodeSerializer,
    responses=inline_serializer(
        name="PhoneVerificationSendCodeResponse",
        fields={
            "detail": serializers.CharField(),
            "data": SendCodeResponseSerializer(),
        },
    ),
)
class ChangePhoneSendCodeView(APIView):
    """
    purpose : change_phone
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = ChangePhoneSendCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone_number = serializer.validated_data["phone_number"]
        purpose = serializer.validated_data["purpose"]

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
    summary="휴대폰 인증코드 확인 - 휴대폰 번호 변경",
    description="휴대폰 번호 변경 목적으로 Twilio Verify를 통해 휴대폰으로 인증코드를 확인합니다. 로그인이 필요합니다.",
    request=ChangePhoneConfirmCodeSerializer,
    responses=inline_serializer(
        name="PhoneVerificationSendCodeResponse",
        fields={
            "detail": serializers.CharField(),
            "data": ConfirmCodeResponseSerializer(),
        },
    ),
)
class ChangePhoneConfirmCodeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        req_serializer = ChangePhoneConfirmCodeSerializer(data=request.data)
        req_serializer.is_valid(raise_exception=True)
        phone_number = req_serializer.validated_data["phone_number"]
        code = req_serializer.validated_data["code"]
        request_id = req_serializer.validated_data["request_id"]
        purpose = req_serializer.validated_data["purpose"]

        result = confirm_code(purpose=purpose, phone_number=phone_number, code=code, request_id=request_id)
        # 서비스가 에러일 때 Response 그대로 반환
        if isinstance(result, Response):
            return result

        resp_serializer = ConfirmCodeResponseSerializer(result)

        return Response(
            {"detail": "인증이 완료되었습니다.", "data": resp_serializer.data},
            status=status.HTTP_200_OK,
        )
