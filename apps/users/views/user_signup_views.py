from __future__ import annotations

from typing import Any, Dict, List, Mapping, cast

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.serializers.user_signup_serializers import (
    SignupResponseSerializer,  # ✅ 오타 수정: SignupResponseSerializerclass -> SignupResponseSerializer
)
from apps.users.serializers.user_signup_serializers import (
    SignupPayload,
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


def to_public_user(user: Any) -> Dict[str, Any]:
    """
    User 모델을 API 응답용 dict로 변환.
    getattr 사용으로 테스트 더블(모의 객체) 호환성도 높임.
    """
    return {
        "id": getattr(user, "id", getattr(user, "pk", None)),
        "email": getattr(user, "email", None),
        "nickname": getattr(user, "nickname", None),
        "name": getattr(user, "name", None),
        "phone_number": getattr(user, "phone_number", None),
        "birthday": getattr(user, "birthday", None),
        "gender": getattr(user, "gender", None),
        "role": getattr(user, "role", "user"),
        "status": status_from_active(getattr(user, "is_active", False)),
        "created_at": getattr(user, "created_at", None),
    }


class UserSignupView(APIView):
    permission_classes = [AllowAny]

    # ✅ 테스트/주입 편의: 서비스 클래스를 속성으로 보관
    SERVICE_CLASS = DefaultSignupService

    @extend_schema(
        operation_id="user_signup",
        tags=["Users"],
        request=UserSignupSerializer,
        responses={201: SignupResponseSerializer},
        summary="사용자 회원가입 API",
        description="이메일/비밀번호 기반 회원 생성.",
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

        # 2) 서비스 호출 (400/409/422 예외 → 일관 포맷)
        try:
            user = self.SERVICE_CLASS().sign_up(payload)

        except DRFValidationError as exc:
            return error(
                "입력값을 확인해주세요.",
                status_code=status.HTTP_400_BAD_REQUEST,
                errors=normalize_errors(exc.detail),
            )

        except APIException as exc:
            # detail과 status_code가 없을 수도 있으니 안전 접근
            formatted = normalize_errors(getattr(exc, "detail", {}))
            code = getattr(exc, "status_code", status.HTTP_500_INTERNAL_SERVER_ERROR)

            if code == status.HTTP_422_UNPROCESSABLE_ENTITY:
                message = "인증 절차가 완료되지 않았습니다."
            elif code == status.HTTP_409_CONFLICT:
                message = "이미 사용 중인 입력값이 있습니다."
            else:
                message = "요청 처리 중 오류가 발생했습니다."

            return error(message, status_code=code, errors=formatted)

        # 3) 성공 (201)
        user_out = UserPublicSerializer(to_public_user(user)).data
        return ok(
            "회원가입에 성공하였습니다.",
            data={"user": user_out},
            status_code=status.HTTP_201_CREATED,
        )
