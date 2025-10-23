from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, cast

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.models.user import User as UserModel
from apps.users.permissions import EmailVerifiedPermission, PhoneVerifiedPermission
from apps.users.serializers.user_signup_serializers import (
    SignupPayload,
    SignupResponseSerializer,
    UserPublicSerializer,
    UserSignupSerializer,
)
from apps.users.services.user_signup_service import (
    DefaultSignupService,
    status_from_active,
)
from apps.users.views.responses import error, ok


# ---------------------------------------------------------------------
# 공통 에러 정규화 유틸
# ---------------------------------------------------------------------
def normalize_errors(detail: Any) -> Dict[str, List[str]]:
    """
    DRF serializer.errors, DRFValidationError.detail, APIException.detail 을
    일관된 dict[str, list[str]] 구조로 변환
    """
    if isinstance(detail, dict):
        out: Dict[str, List[str]] = {}
        for k, v in detail.items():
            if isinstance(v, (list, tuple)):
                out[k] = [str(x) for x in v]
            else:
                out[k] = [str(v)]
        return out

    if isinstance(detail, (list, tuple)):
        return {"non_field_errors": [str(x) for x in detail]}

    return {"non_field_errors": [str(detail)]}


def to_public_user(user: "UserModel") -> Dict[str, Any]:
    """응답 생성용 공개 사용자 dict 변환 유틸"""
    return {
        "email": getattr(user, "email", None),
        "nickname": getattr(user, "nickname", None),
        "name": getattr(user, "name", None),
        "phone_number": getattr(user, "phone_number", None),
        "birthday": getattr(user, "birthday", None),
        "gender": getattr(user, "gender", None),
        "status": status_from_active(bool(getattr(user, "is_active", False))),
        "created_at": getattr(user, "created_at", None),
    }


# ---------------------------------------------------------------------
# 서비스 타입 프로토콜 (테스트/의존성 주입 용)
# ---------------------------------------------------------------------
class SignupServiceProto(Protocol):
    def sign_up(self, payload: SignupPayload) -> UserModel: ...


# ---------------------------------------------------------------------
# 회원가입 뷰
# ---------------------------------------------------------------------
class UserSignupView(APIView):
    """
    이메일+휴대폰 인증(verify_token) 완료 후 회원가입 처리.
    Permission 단계에서 이미 토큰 검증/소비가 끝난 상태.
    """

    permission_classes = [EmailVerifiedPermission, PhoneVerifiedPermission]
    purpose = "signup"

    SERVICE_CLASS: type[SignupServiceProto] = DefaultSignupService

    @extend_schema(
        operation_id="user_signup",
        tags=["Users"],
        request=UserSignupSerializer,
        responses={
            201: SignupResponseSerializer,
        },
        summary="사용자 회원가입 API",
        description="이메일/휴대폰 인증 완료 후 계정 생성.",
    )
    def post(self, request: Request) -> Response:
        # 1) 요청 스키마 검증 (400)
        serializer = UserSignupSerializer(data=request.data)
        if not serializer.is_valid():
            return error(
                "입력값을 확인해주세요.",
                status_code=status.HTTP_400_BAD_REQUEST,
                errors=normalize_errors(serializer.errors),
            )

        payload: SignupPayload = cast(SignupPayload, serializer.validated_data)

        # 2) verify 토큰의 sub 값과 요청값 일치 검증
        claims_email: Optional[Dict[str, Any]] = cast(
            Optional[Dict[str, Any]], getattr(request, "email_verify_claims", None)
        )
        if claims_email and str(claims_email.get("sub", "")).strip().lower() != str(payload["email"]).strip().lower():
            return error(
                "인증 이메일과 요청 이메일이 일치하지 않습니다.",
                status_code=status.HTTP_400_BAD_REQUEST,
                errors={"email": ["인증된 이메일과 불일치합니다."]},
            )

        claims_phone: Optional[Dict[str, Any]] = cast(
            Optional[Dict[str, Any]], getattr(request, "phone_verify_claims", None)
        )
        if claims_phone and str(claims_phone.get("sub", "")) != str(payload["phone_number"]):
            return error(
                "인증 휴대폰과 요청 휴대폰이 일치하지 않습니다.",
                status_code=status.HTTP_400_BAD_REQUEST,
                errors={"phone_number": ["인증된 휴대폰과 불일치합니다."]},
            )

        # 3) 서비스 호출 (400/409/422 예외 처리)
        try:
            user = self.SERVICE_CLASS().sign_up(payload)
        except DRFValidationError as exc:
            return error(
                "입력값을 확인해주세요.",
                status_code=status.HTTP_400_BAD_REQUEST,
                errors=normalize_errors(exc.detail),
            )
        except APIException as exc:
            formatted = normalize_errors(getattr(exc, "detail", {}))
            code = getattr(exc, "status_code", status.HTTP_500_INTERNAL_SERVER_ERROR)

            if code == status.HTTP_422_UNPROCESSABLE_ENTITY:
                message = "인증 절차가 완료되지 않았습니다."
            elif code == status.HTTP_409_CONFLICT:
                message = "이미 사용 중인 입력값이 있습니다."
            else:
                message = "요청 처리 중 오류가 발생했습니다."

            return error(message, status_code=code, errors=formatted)

        # 4) 성공 (201) — 스키마 전용 Serializer에 dict 주입
        user_out = UserPublicSerializer(to_public_user(user)).data
        return ok(
            "회원가입에 성공하였습니다.",
            data={"user": user_out},
            status_code=status.HTTP_201_CREATED,
        )
