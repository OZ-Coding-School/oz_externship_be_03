from __future__ import annotations

from drf_spectacular.utils import extend_schema, OpenApiExample
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.serializers.phone_verification_serializers import (
    ConfirmCodeSerializer,
    SendCodeSerializer, SendCodeResponseSerializer, ConfirmCodeResponseSerializer,
)
from apps.users.services.phone_verification import confirm_code, send_code

@extend_schema(
    tags=["Users"],
    summary="휴대폰 인증코드 전송",
    description="Twilio Verify를 통해 휴대폰으로 인증코드를 전송합니다.",
    request=SendCodeSerializer,
    responses=SendCodeResponseSerializer,
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

        send_code(purpose=purpose, phone_number=phone_number)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    tags=["Users"],
    summary="휴대폰 인증코드 확인",
    description="사용자가 받은 인증코드를 검증합니다. 성공 시 이후 단계에서 소비할 원타임 키가 저장됩니다.",
    request=ConfirmCodeSerializer,
    responses=ConfirmCodeResponseSerializer,
)
class PhoneConfirmCodeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = ConfirmCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        purpose = serializer.validated_data["purpose"]
        phone_number = serializer.validated_data["phone_number"]
        code = serializer.validated_data["code"]

        # 로그인 상태면 user_id를 전달해 Redis subject를 유저 기준으로 남김
        user_id = request.user.id if getattr(request, "user", None) and request.user.is_authenticated else None
        confirm_code(purpose=purpose, phone_number=phone_number, code=code, user_id=user_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
