from __future__ import annotations

from typing import Any, Optional

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.serializers.social_auth_serializers import (
    SocialAuthRequestSerializer,
    SocialAuthResponseSerializer,
)
from apps.users.services.social_auth_services import SocialAuthService


class SocialAuthView(APIView):

    permission_classes = [AllowAny]

    @extend_schema(
        tags=["SocialAuth"],
        summary="소셜 로그인 (카카오 / 네이버)",
        request=SocialAuthRequestSerializer,
        responses={200: SocialAuthResponseSerializer},
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        provider_raw = kwargs.get("provider")

        if not isinstance(provider_raw, str) or provider_raw not in ("kakao", "naver"):
            return Response(
                {"error": f"지원하지 않는 provider입니다: {provider_raw}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        provider: str = provider_raw

        serializer = SocialAuthRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        code: str = serializer.validated_data["code"]
        state: Optional[str] = serializer.validated_data.get("state")

        try:
            result = SocialAuthService.handle_social_login(provider, code, state)

            response_serializer = SocialAuthResponseSerializer.from_service_result(result)
            response = Response(response_serializer.data, status=status.HTTP_200_OK)

            refresh_token = result.get("data", {}).get("refresh")
            if refresh_token:
                response.set_cookie(
                    key="refresh_token",
                    value=refresh_token,
                    httponly=True,
                    secure=True,
                    samesite="None",
                )

            return response

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
