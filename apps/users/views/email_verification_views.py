from __future__ import annotations

from typing import Any, Dict, Tuple, Type, Union, cast

from django.utils.module_loading import import_string
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.authentication import BaseAuthentication
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.settings import api_settings

from apps.core.views import ExceptionHandledAPIView
from apps.users.enums import EmailVerificationPurpose
from apps.users.serializers.email_verification_serializers import (
    EmailVerificationRequestSerializer,
    EmailVerificationSendCodeResponseSerializer,
    EmailVerifyCodeResponseSerializer,
    EmailVerifyCodeSerializer,
)
from apps.users.services import email_verification_services as svc


def _resolve_default_auth_classes() -> Tuple[Type[BaseAuthentication], ...]:
    resolved: list[Type[BaseAuthentication]] = []
    for item in api_settings.DEFAULT_AUTHENTICATION_CLASSES:
        resolved.append(import_string(item) if isinstance(item, str) else item)
    return tuple(resolved)


AUTH_CLASSES_DEFAULT: Tuple[Type[BaseAuthentication], ...] = _resolve_default_auth_classes()


# =============================================================================
# 내부 헬퍼
# =============================================================================
def _build_send_payload(*, email: str, purpose: EmailVerificationPurpose) -> Dict[str, Any]:
    """
    이메일 인증코드 전송용 페이로드 빌더
    purpose 자동 주입
    """
    return {"email": email, "purpose": purpose}


def _build_confirm_payload(
    *, email: str, verification_code: str, request_id: str, purpose: EmailVerificationPurpose
) -> Dict[str, Any]:
    """
    이메일 인증코드 확인용 페이로드 빌더
    purpose 자동 주입
    """
    return {
        "email": email,
        "verification_code": verification_code,
        "request_id": request_id,
        "purpose": purpose,
    }


# =============================================================================
# 공통뷰: 이메일 인증코드 전송
# =============================================================================
class _BaseEmailSendCodeView(ExceptionHandledAPIView):
    """
    이메일 인증코드 전송 공통 베이스
    - 하위 클래스에서 authentication_classes / permission_classes / PURPOSE 지정
    """

    authentication_classes = cast(Tuple[Type[BaseAuthentication], ...], ())
    permission_classes = cast(Tuple[Type[BasePermission], ...], (AllowAny,))

    PURPOSE: Any | None = None

    @extend_schema(exclude=True)
    def post(self, request: Request) -> Response:
        ser = EmailVerificationRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email: str = cast(str, ser.validated_data["email"])

        purpose = cast(Any, self.PURPOSE)
        assert purpose is not None, "PURPOSE 지정이 필요합니다."

        payload = _build_send_payload(email=email, purpose=purpose)
        result: Union[Response, Dict[str, Any]] = svc.email_send_code(**payload)
        if isinstance(result, Response):
            return result

        meta = EmailVerificationSendCodeResponseSerializer(result).data
        purpose_value = getattr(purpose, "value", str(purpose))
        return Response(
            {"detail": "인증코드를 발송했습니다.", "purpose": purpose_value, "data": meta},
            status=status.HTTP_200_OK,
        )


# =============================================================================
# 공통뷰: 이메일 인증코드 확인
# =============================================================================
class _BaseEmailConfirmCodeView(ExceptionHandledAPIView):
    """
    이메일 인증코드 확인 공통 베이스
    """

    authentication_classes = cast(Tuple[Type[BaseAuthentication], ...], ())
    permission_classes = cast(Tuple[Type[BasePermission], ...], (AllowAny,))
    PURPOSE: Any | None = None

    @extend_schema(exclude=True)
    def post(self, request: Request) -> Response:
        ser = EmailVerifyCodeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        email: str = cast(str, ser.validated_data["email"])
        verification_code: str = cast(str, ser.validated_data["verification_code"])
        request_id: str = cast(str, ser.validated_data["request_id"])

        purpose = cast(Any, self.PURPOSE)
        assert purpose is not None, "PURPOSE 지정이 필요합니다."

        payload = _build_confirm_payload(
            email=email, verification_code=verification_code, request_id=request_id, purpose=purpose
        )
        result: Union[Response, Dict[str, Any]] = svc.email_confirm_code(**payload)
        if isinstance(result, Response):
            return result

        meta = EmailVerifyCodeResponseSerializer(result).data
        purpose_value = getattr(purpose, "value", str(purpose))
        return Response(
            {"detail": "인증이 완료되었습니다.", "purpose": purpose_value, "data": meta},
            status=status.HTTP_200_OK,
        )


# =============================================================================
# 회원가입(SIGNUP)
# =============================================================================
class SignupEmailSendCodeView(_BaseEmailSendCodeView):
    PURPOSE = EmailVerificationPurpose.SIGNUP

    @extend_schema(
        operation_id="email_send_code_signup",
        tags=["Users"],
        summary="이메일 인증코드 전송 - 회원가입",
        description="회원가입 목적의 이메일 인증코드 발송",
        request=EmailVerificationRequestSerializer,
        responses={
            200: EmailVerificationSendCodeResponseSerializer,
            400: OpenApiResponse(description="요청 본문 검증 실패"),
            429: OpenApiResponse(description="재전송 쿨다운/시도 제한"),
            500: OpenApiResponse(description="서버 오류"),
        },
    )
    def post(self, request: Request) -> Response:
        return super().post(request=request)


class SignupEmailConfirmCodeView(_BaseEmailConfirmCodeView):
    PURPOSE = EmailVerificationPurpose.SIGNUP

    @extend_schema(
        operation_id="email_confirm_code_signup",
        tags=["Users"],
        summary="이메일 인증코드 확인 - 회원가입",
        description="회원가입 목적의 이메일 인증코드를 확인",
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
    def post(self, request: Request) -> Response:
        return super().post(request)


# =============================================================================
# 비밀번호 재설정(RESET_PASSWORD)
# =============================================================================
class ResetPasswordEmailSendCodeView(_BaseEmailSendCodeView):
    PURPOSE = EmailVerificationPurpose.RESET_PASSWORD

    @extend_schema(
        operation_id="email_send_code_reset_password",
        tags=["Users"],
        summary="이메일 인증코드 전송 - 비밀번호 재설정",
        description="비밀번호 재설정 목적의 이메일 인증코드를 발송",
        request=EmailVerificationRequestSerializer,
        responses={
            200: EmailVerificationSendCodeResponseSerializer,
            400: OpenApiResponse(description="요청 본문 검증 실패"),
            429: OpenApiResponse(description="재전송 쿨다운/시도 제한"),
            500: OpenApiResponse(description="서버 오류"),
        },
    )
    def post(self, request: Request) -> Response:
        return super().post(request)


class ResetPasswordEmailConfirmCodeView(_BaseEmailConfirmCodeView):
    PURPOSE = EmailVerificationPurpose.RESET_PASSWORD

    @extend_schema(
        operation_id="email_confirm_code_reset_password",
        tags=["Users"],
        summary="이메일 인증코드 확인 - 비밀번호 재설정",
        description="비밀번호 재설정 목적의 이메일 인증코드를 확인",
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
    def post(self, request: Request) -> Response:
        return super().post(request)


# =============================================================================
# 탈퇴계정 복구(RESTORE_USER)
# =============================================================================
class RestoreUserEmailSendCodeView(_BaseEmailSendCodeView):
    PURPOSE = EmailVerificationPurpose.RESTORE_USER

    @extend_schema(
        operation_id="email_send_code_restore_user",
        tags=["Users"],
        summary="이메일 인증코드 전송 - 탈퇴계정 복구",
        description="탈퇴계정 복구 목적의 이메일 인증코드를 발송",
        request=EmailVerificationRequestSerializer,
        responses={
            200: EmailVerificationSendCodeResponseSerializer,
            400: OpenApiResponse(description="요청 본문 검증 실패"),
            429: OpenApiResponse(description="재전송 쿨다운/시도 제한"),
            500: OpenApiResponse(description="서버 오류"),
        },
    )
    def post(self, request: Request) -> Response:
        return super().post(request)


class RestoreUserEmailConfirmCodeView(_BaseEmailConfirmCodeView):
    PURPOSE = EmailVerificationPurpose.RESTORE_USER

    @extend_schema(
        operation_id="email_confirm_code_restore_user",
        tags=["Users"],
        summary="이메일 인증코드 확인 - 탈퇴계정 복구",
        description="탈퇴계정 복구 목적의 이메일 인증코드를 확인",
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
    def post(self, request: Request) -> Response:
        return super().post(request)


# =============================================================================
# 이메일 변경(CHANGE_EMAIL)
# =============================================================================
class ChangeEmailSendCodeView(_BaseEmailSendCodeView):
    PURPOSE = EmailVerificationPurpose.CHANGE_EMAIL

    permission_classes = cast(Tuple[Type[BasePermission], ...], (IsAuthenticated,))
    authentication_classes = AUTH_CLASSES_DEFAULT

    @extend_schema(
        operation_id="email_send_code_change_email",
        tags=["Users"],
        summary="이메일 인증코드 전송 - 이메일 변경",
        description="이메일 변경 목적의 이메일 인증코드를 발송",
        request=EmailVerificationRequestSerializer,
        responses={
            200: EmailVerificationSendCodeResponseSerializer,
            400: OpenApiResponse(description="요청 본문 검증 실패"),
            429: OpenApiResponse(description="재전송 쿨다운/시도 제한"),
            500: OpenApiResponse(description="서버 오류"),
        },
    )
    def post(self, request: Request) -> Response:
        return super().post(request)


class ChangeEmailConfirmCodeView(_BaseEmailConfirmCodeView):
    PURPOSE = EmailVerificationPurpose.CHANGE_EMAIL

    permission_classes = cast(Tuple[Type[BasePermission], ...], (IsAuthenticated,))
    authentication_classes = AUTH_CLASSES_DEFAULT

    @extend_schema(
        operation_id="email_confirm_code_change_email",
        tags=["Users"],
        summary="이메일 인증코드 확인 - 이메일 변경",
        description="이메일 변경 목적의 이메일 인증코드를 확인",
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
    def post(self, request: Request) -> Response:
        return super().post(request)
