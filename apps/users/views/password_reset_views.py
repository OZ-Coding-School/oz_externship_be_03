from __future__ import annotations

from typing import Optional

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.enums import EmailVerificationPurpose
from apps.users.permissions import EmailVerifiedPermission
from apps.users.serializers.password_reset_serializers import PasswordResetSerializer
from apps.users.services.password_reset_services import reset_password


def _header(request: Request, name: str) -> Optional[str]:
    return request.headers.get(name)


@extend_schema(
    tags=["Users"],
    summary="비밀번호 재설정",
    description="이메일 인증을 거친 뒤 비밀번호를 재설정합니다.",
    request=PasswordResetSerializer,
    parameters=[
        OpenApiParameter(
            name="X-Email-Verify-Token",
            type=str,
            location=OpenApiParameter.HEADER,
            required=True,
            description="이메일 인증 토큰",
        ),
        OpenApiParameter(
            name="Idempotency-Key",
            type=str,
            location=OpenApiParameter.HEADER,
            required=False,
            description="중복 요청 방지 키 (UUID 권장)",
        ),
    ],
)
class PasswordResetView(APIView):
    permission_classes = [AllowAny, EmailVerifiedPermission]
    purpose = EmailVerificationPurpose.RESET_PASSWORD

    def post(self, request: Request) -> Response:
        claims = getattr(request, "email_verify_claims", None)
        if not claims:
            return Response({"error": "토큰이 유효하지 않습니다."}, status=status.HTTP_401_UNAUTHORIZED)

        req_serializer = PasswordResetSerializer(data=request.data)
        req_serializer.is_valid(raise_exception=True)

        idem_key = _header(request, "Idempotency-Key")

        reset_password(
            claims=claims,
            new_password=req_serializer.validated_data["new_password"],
            new_password_confirm=req_serializer.validated_data["new_password_confirm"],
            idempotency_key=idem_key,
        )

        return Response({"detail": "비밀번호가 재설정되었습니다."}, status=status.HTTP_200_OK)
