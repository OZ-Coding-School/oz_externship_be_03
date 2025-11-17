from __future__ import annotations

from typing import Any, Dict, Optional, cast

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from apps.users.enums import EmailVerificationPurpose
from apps.users.permissions import EmailVerifiedPermission, PhoneVerifiedPermission
from apps.users.serializers.user_signup_serializers import (
    SignupPayload,
    UserSignupSerializer,
)
from apps.users.services.user_signup_service import (
    DefaultSignupService,
)
from apps.users.utils.response_helpers import ok
from apps.users.views.base import SignupExceptionHandledAPIView


# ---------------------------------------------------------------------
# 회원가입 뷰
# ---------------------------------------------------------------------
class UserSignupView(SignupExceptionHandledAPIView):
    """
    이메일+휴대폰 인증(verify_token) 완료 후 회원가입 처리.
    Permission 단계에서 이미 토큰 검증/소비가 끝난 상태.
    """

    # 회원가입에서는 인증 비활성화 필요
    authentication_classes: tuple[type[BaseAuthentication], ...] = ()

    permission_classes = [EmailVerifiedPermission, PhoneVerifiedPermission]
    purpose = EmailVerificationPurpose.SIGNUP

    SERVICE_CLASS = DefaultSignupService

    @extend_schema(
        operation_id="user_signup",
        tags=["Users"],
        request=UserSignupSerializer,
        responses={
            201,
        },
        summary="사용자 회원가입 API",
        description="이메일/휴대폰 인증 완료 후 계정 생성.",
        parameters=[
            OpenApiParameter(
                name="X-Email-Verify-Token",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.HEADER,
                required=True,
                description="이메일 검증 토큰(헤더)",
            ),
            OpenApiParameter(
                name="X-Phone-Verify-Token",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.HEADER,
                required=True,
                description="휴대폰 검증 토큰(헤더)",
            ),
        ],
    )
    def post(self, request: Request) -> Response:
        # 1) 요청 스키마 검증 (400)
        serializer = UserSignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload: SignupPayload = cast(SignupPayload, serializer.validated_data)

        # 2) verify 토큰의 sub 값과 요청값 일치 검증
        claims_email: Optional[Dict[str, Any]] = cast(
            Optional[Dict[str, Any]], getattr(request, "email_verify_claims", None)
        )
        if claims_email and str(claims_email.get("sub", "")).strip().lower() != str(payload["email"]).strip().lower():
            raise ValidationError({"email": ["인증된 이메일과 불일치합니다."]})

        claims_phone: Optional[Dict[str, Any]] = cast(
            Optional[Dict[str, Any]], getattr(request, "phone_verify_claims", None)
        )
        if claims_phone and str(claims_phone.get("sub", "")) != str(payload["phone_number"]):
            raise ValidationError({"phone_number": ["인증된 휴대폰과 불일치합니다."]})

        # 3) 서비스 호출
        service = self.SERVICE_CLASS()
        service.sign_up(payload)

        # 4) 성공
        return ok("회원가입에 성공하였습니다.", status_code=status.HTTP_201_CREATED)
