from typing import Any

from drf_spectacular.utils import OpenApiResponse, extend_schema
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


@extend_schema(
    tags=["Auth"],
    summary="소셜 로그인 (카카오 / 네이버)",
    description="provider(kakao/naver)에 따라 인가 코드(code) 및 state를 이용해 로그인 또는 회원가입을 처리합니다.",
    request=SocialAuthRequestSerializer,
    responses={
        200: SocialAuthResponseSerializer,
        400: OpenApiResponse(description="요청 형식이 올바르지 않습니다."),
        401: OpenApiResponse(description="유효하지 않은 토큰입니다."),
    },
)
class SocialAuthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: tuple[Any, ...] = ()

    def post(self, request: Request, provider: str, *args: Any, **kwargs: Any) -> Response:

        serializer = SocialAuthRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data["code"]
        state = serializer.validated_data.get("state")

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
