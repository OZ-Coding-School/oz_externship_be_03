from __future__ import annotations

from typing import Optional

from django.contrib.auth import get_user_model
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.authentication import BaseAuthentication
from rest_framework.request import Request
from rest_framework.response import Response

from apps.core.views import ExceptionHandledAPIView
from apps.users.enums import PhoneVerificationPurpose
from apps.users.permissions import PhoneVerifiedPermission
from apps.users.serializers.find_email_serializers import FindEmailSerializer
from apps.users.utils.phone_normalize import denormalize_kr_phone

User = get_user_model()


def _header(request: Request, name: str) -> Optional[str]:
    return request.headers.get(name)


@extend_schema(
    tags=["Users"],
    summary="이메일 찾기",
    description="휴대폰 인증을 거친 뒤 이메일을 찾습니다.",
    responses=inline_serializer(
        name="FindEmailResponse",
        fields={
            "detail": serializers.CharField(),
            "data": FindEmailSerializer(),
        },
    ),
    parameters=[
        OpenApiParameter(
            name="X-Phone-Verify-Token",
            type=str,
            location=OpenApiParameter.HEADER,
            required=True,
            description="휴대폰 인증 토큰",
        ),
    ],
)
class FindEmailView(ExceptionHandledAPIView):
    # 인증 비활성화
    authentication_classes: tuple[type[BaseAuthentication], ...] = ()
    permission_classes = [PhoneVerifiedPermission]
    purpose = PhoneVerificationPurpose.FIND_EMAIL

    def get(self, request: Request) -> Response:
        claims = getattr(request, "phone_verify_claims", None)
        if not claims:
            return Response({"error": "토큰이 유효하지 않습니다."}, status=status.HTTP_401_UNAUTHORIZED)

        phone = claims.get("to")
        try:
            user = User.objects.get(phone_number=denormalize_kr_phone(phone), is_active=True)
        except User.DoesNotExist:
            return Response({"error": "존재하지 않는 사용자입니다."}, status=status.HTTP_404_NOT_FOUND)

        serializer = FindEmailSerializer({"email": user.email})
        return Response(
            {"detail": "이메일 찾기 완료.", "data": serializer.data},
            status=status.HTTP_200_OK,
        )
