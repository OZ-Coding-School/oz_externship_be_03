from __future__ import annotations

from typing import Any, Optional, Union

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.enums import EmailVerificationPurpose, PhoneVerificationPurpose
from apps.users.utils.verify_token import verify_and_consume


class PhoneVerifiedPermission(BasePermission):
    """
    휴대폰 인증 퍼미션 (검증 토큰 기반)

    - 뷰나 퍼미션에 지정된 purpose에 대해 검증 토큰을 헤더 또는 본문 제출해야 통과
    - 헤더: X-Phone-Verify-Token
    - expected_sub: 휴대폰 번호
    - 통과 시 토큰은 즉시 소비(원타임)되며, request.phone_verify_claims에 클레임 저장
    사용 예)
        class MyView(APIView):
            permission_classes = [IsAuthenticated, PhoneVerifiedPermission]
            purpose = "change_phone"  # ← 여기서 목적 지정
    """

    message = "휴대폰 인증이 완료되지 않았습니다."
    purpose: Optional[PhoneVerificationPurpose] = None
    header_name = "X-Phone-Verify-Token"

    def has_permission(self, request: Request, view: APIView) -> bool:
        purpose: Optional[PhoneVerificationPurpose] = getattr(view, "purpose", self.purpose)
        if not purpose:
            self.message = "인증 목적이 지정되지 않았습니다."
            return False

        # 헤더 우선, 본문 대체 허용
        token = request.headers.get(self.header_name)
        if not token:
            token = request.data.get("verify_token")

        if not token:
            self.message = "검증 토큰이 필요합니다."
            return False

        phone_number = request.data.get("phone_number") or request.query_params.get("phone_number")
        if not phone_number:
            self.message = "전화번호가 필요합니다."
            return False

        try:
            claims = verify_and_consume(
                token, expected_purpose=purpose, expected_sub=phone_number  # 목적 강제  # 주체 강제
            )
            # 뷰 로직에서 참조 가능하도록 저장(옵션)
            setattr(request, "phone_verify_claims", claims)
            return True
        except ValueError as e:
            self.message = str(e) or self.message
            return False


class EmailVerifiedPermission(BasePermission):
    """
    이메일 인증 퍼미션 (검증 토큰 기반)

    - 이메일 인증 흐름에도 동일한 검증 토큰 방식을 적용
    - 헤더: X-Email-Verify-Token
    - expected_sub: 로그인 사용자 id (또는 시나리오에 따라 이메일/세션키로 커스터마이즈)
    - 통과 시 토큰은 즉시 소비(원타임)되며, request.email_verify_claims에 클레임 저장
    사용 예)
        class SomeEmailBoundView(APIView):
            permission_classes = [IsAuthenticated, EmailVerifiedPermission]
            purpose = "change_email"
    """

    message = "이메일 인증이 완료되지 않았습니다."
    purpose: Optional[EmailVerificationPurpose] = None
    header_name = "X-Email-Verify-Token"

    def has_permission(self, request: Request, view: APIView) -> bool:
        purpose: Optional[EmailVerificationPurpose] = getattr(view, "purpose", self.purpose)
        if not purpose:
            self.message = "인증 목적이 지정되지 않았습니다."
            return False

        # 헤더 우선, 본문 대체 허용
        token = request.headers.get(self.header_name) or request.data.get("verify_token")
        if not token:
            self.message = "검증 토큰이 필요합니다."
            return False

        email = request.data.get("email") or request.query_params.get("email")
        if not email:
            self.message = "이메일이 필요합니다."
            return False

        result: Union[dict[str, Any], Response] = verify_and_consume(
            token, expected_purpose=purpose, expected_sub=email
        )
        if isinstance(result, Response):
            self.message = str(result.data.get("error", self.message))
            return False

        setattr(request, "email_verify_claims", result)
        return True
