from __future__ import annotations

from typing import Callable, Tuple, Type, cast

from drf_spectacular.utils import F, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.authentication import BaseAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.enums import PhoneVerificationPurpose
from apps.users.serializers.phone_verification_serializers import (
    ConfirmCodeResponseSerializer,
    ConfirmCodeSerializer,
    SendCodeResponseSerializer,
    SendCodeSerializer,
)
from apps.users.services.phone_verification_services import confirm_code, send_code
from apps.users.views.email_verification_views import AUTH_CLASSES_DEFAULT

# -------------------------------
# 공통 부분
# -------------------------------


def phone_send_schema(summary: str, description: str) -> Callable[[F], F]:
    """
    휴대폰 인증코드 전송용 공통 extend_schema 데코레이터 팩토리
    """
    return extend_schema(
        tags=["Users"],
        summary=summary,
        description=description,
        request=SendCodeSerializer,
        responses=inline_serializer(
            name="PhoneVerificationSendCodeResponse",
            fields={
                "detail": serializers.CharField(),
                "data": SendCodeResponseSerializer(),
            },
        ),
    )


class BasePhoneSendCodeView(APIView):
    """
    휴대폰 인증코드 전송 공통 베이스
    - 하위 클래스에서 PURPOSE / permission_classes 만 지정
    """

    PURPOSE: PhoneVerificationPurpose

    def post(self, request: Request) -> Response:
        req_serializer = SendCodeSerializer(data=request.data)
        req_serializer.is_valid(raise_exception=True)
        phone_number = req_serializer.validated_data["phone_number"]

        result = send_code(
            purpose=self.PURPOSE,
            phone_number=phone_number,
        )
        if isinstance(result, Response):
            return result

        resp_serializer = SendCodeResponseSerializer(result)
        return Response(
            {"detail": "인증코드를 발송했습니다.", "data": resp_serializer.data},
            status=status.HTTP_200_OK,
        )


def phone_confirm_schema(summary: str, description: str) -> Callable[[F], F]:
    """
    휴대폰 인증코드 확인용 공통 extend_schema 데코레이터 팩토리
    """
    return extend_schema(
        tags=["Users"],
        summary=summary,
        description=description,
        request=ConfirmCodeSerializer,
        responses=inline_serializer(
            name="PhoneVerificationConfirmCodeResponse",
            fields={
                "detail": serializers.CharField(),
                "data": ConfirmCodeResponseSerializer(),
            },
        ),
    )


class BasePhoneConfirmCodeView(APIView):
    """
    휴대폰 인증코드 확인 공통 베이스
    - 하위 클래스에서 PURPOSE / permission_classes 만 지정
    """

    PURPOSE: PhoneVerificationPurpose

    def post(self, request: Request) -> Response:
        req_serializer = ConfirmCodeSerializer(data=request.data)
        req_serializer.is_valid(raise_exception=True)
        phone_number = req_serializer.validated_data["phone_number"]
        code = req_serializer.validated_data["code"]
        request_id = req_serializer.validated_data["request_id"]

        result = confirm_code(purpose=self.PURPOSE, phone_number=phone_number, code=code, request_id=request_id)
        # 서비스가 에러일 때 Response 그대로 반환
        if isinstance(result, Response):
            return result

        resp_serializer = ConfirmCodeResponseSerializer(result)

        return Response(
            {"detail": "인증이 완료되었습니다.", "data": resp_serializer.data},
            status=status.HTTP_200_OK,
        )


# -------------------------------
# 회원가입 목적 휴대폰 인증 코드
# -------------------------------


@phone_send_schema(
    summary="휴대폰 인증코드 전송 - 회원가입",
    description="회원가입 목적으로 Twilio Verify를 통해 휴대폰으로 인증코드를 전송합니다. 로그인이 필요하지 않습니다.",
)
class SignupSendCodeView(BasePhoneSendCodeView):
    permission_classes = [AllowAny]
    PURPOSE = PhoneVerificationPurpose.SIGNUP
    authentication_classes = cast(Tuple[Type[BaseAuthentication], ...], ())


@phone_confirm_schema(
    summary="휴대폰 인증코드 확인 - 회원가입",
    description="회원가입 목적으로 Twilio Verify를 통해 휴대폰으로 인증코드를 확인합니다. 로그인이 필요하지 않습니다.",
)
class SignupConfirmCodeView(BasePhoneConfirmCodeView):
    permission_classes = [AllowAny]
    PURPOSE = PhoneVerificationPurpose.SIGNUP
    authentication_classes = cast(Tuple[Type[BaseAuthentication], ...], ())


# -------------------------------
# 이메일 찾기 목적 휴대폰 인증 코드
# -------------------------------


@phone_send_schema(
    summary="휴대폰 인증코드 전송 - 이메일 찾기",
    description="이메일 찾기 목적으로 Twilio Verify를 통해 휴대폰으로 인증코드를 전송합니다. 로그인이 필요하지 않습니다.",
)
class FindEmailSendCodeView(BasePhoneSendCodeView):
    permission_classes = [AllowAny]
    PURPOSE = PhoneVerificationPurpose.FIND_EMAIL
    authentication_classes = cast(Tuple[Type[BaseAuthentication], ...], ())


@phone_confirm_schema(
    summary="휴대폰 인증코드 확인 - 이메일 찾기",
    description="이메일 찾기 목적으로 Twilio Verify를 통해 휴대폰으로 인증코드를 확인합니다. 로그인이 필요하지 않습니다..",
)
class FindEmailConfirmCodeView(BasePhoneConfirmCodeView):
    permission_classes = [AllowAny]
    PURPOSE = PhoneVerificationPurpose.FIND_EMAIL
    authentication_classes = cast(Tuple[Type[BaseAuthentication], ...], ())


# -------------------------------
# 휴대폰 번호 변경 목적 휴대폰 인증 코드
# -------------------------------


@phone_send_schema(
    summary="휴대폰 인증코드 전송 - 휴대폰 번호 변경",
    description="휴대폰 번호 변경 목적으로 Twilio Verify를 통해 휴대폰으로 인증코드를 전송합니다. 로그인이 필요합니다.",
)
class ChangePhoneSendCodeView(BasePhoneSendCodeView):
    PURPOSE = PhoneVerificationPurpose.CHANGE_PHONE
    permission_classes = [IsAuthenticated]
    authentication_classes = AUTH_CLASSES_DEFAULT


@phone_confirm_schema(
    summary="휴대폰 인증코드 확인 - 휴대폰 번호 변경",
    description="휴대폰 번호 변경 목적으로 Twilio Verify를 통해 휴대폰으로 인증코드를 확인합니다. 로그인이 필요합니다.",
)
class ChangePhoneConfirmCodeView(BasePhoneConfirmCodeView):
    PURPOSE = PhoneVerificationPurpose.CHANGE_PHONE
    permission_classes = [IsAuthenticated]
    authentication_classes = AUTH_CLASSES_DEFAULT
