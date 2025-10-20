from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.serializers.phone_verification_serializers import (
    PhoneVerificationConfirmCodeSerializer,
    PhoneVerificationSendCodeSerializer,
)
from apps.users.services.phone_verification import confirm_code, send_code


class PhoneSendCodeView(APIView):
    """
    목적(purpose)에 따라 권한 정책:
    - signup / find_email / reset_password : AllowAny
    - change_phone : 로그인 필요
    """

    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        ser = PhoneVerificationSendCodeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        purpose = ser.validated_data["purpose"]
        phone_number = ser.validated_data["phone_number"]

        # 권한 분기
        if purpose == "change_phone" and not request.user.is_authenticated:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        send_code(purpose=purpose, phone_number=phone_number)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PhoneConfirmCodeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        ser = PhoneVerificationConfirmCodeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        purpose = ser.validated_data["purpose"]
        phone_number = ser.validated_data["phone_number"]
        code = ser.validated_data["code"]

        # 로그인 상태면 user_id를 전달해 Redis subject를 유저 기준으로 남김
        user_id = request.user.id if getattr(request, "user", None) and request.user.is_authenticated else None
        confirm_code(purpose=purpose, phone_number=phone_number, code=code, user_id=user_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
