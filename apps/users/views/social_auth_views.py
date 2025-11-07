from __future__ import annotations

from typing import Any, Optional

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken

from apps.users.serializers.social_auth_serializers import (
    KakaoAuthRequestSerializer,
    NaverAuthRequestSerializer,
    SocialAuthResponseSerializer,
)
from apps.users.services.social_auth_services import SocialAuthService


class BaseSocialAuthView(APIView):

    authentication_classes = []
    permission_classes = [AllowAny]
    provider: str
    provider_label: str

    def handle_exception(self, exc: Exception) -> Response:
        """
        ❗모든 예외를 통일된 구조로 처리
        """
        message = str(exc)

        # 🔹 401 인증 관련
        if isinstance(exc, (AuthenticationFailed, InvalidToken)):
            return Response(
                {"error": f"유효하지 않은 {self.provider_label} 토큰입니다. 다시 로그인해주세요."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # 🔹 403 권한 거부
        if isinstance(exc, PermissionDenied):
            return Response(
                {"error": f"{self.provider_label} 접근 권한이 없습니다."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # 🔹 일반 요청 오류 (400)
        if isinstance(exc, (ValueError, KeyError)):
            return Response(
                {"error": f"요청 형식이 올바르지 않습니다. ({self.provider_label})"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({"error": message}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    tags=["Auth"],
    summary="카카오 소셜 로그인",
    description="카카오 OAuth 인가 코드(code)로 로그인 또는 회원가입을 처리합니다.",
    request=KakaoAuthRequestSerializer,
    responses={
        200: SocialAuthResponseSerializer,
        400: OpenApiResponse(description="요청 형식이 올바르지 않습니다."),
        401: OpenApiResponse(description="유효하지 않은 카카오 토큰입니다."),
        403: OpenApiResponse(description="카카오 접근 권한이 없습니다."),
    },
)
class KakaoAuthView(BaseSocialAuthView):
    provider = "kakao"
    provider_label = "카카오"

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = KakaoAuthRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code: str = serializer.validated_data["code"]

        result = SocialAuthService.handle_social_login(self.provider, code)
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


@extend_schema(
    tags=["Auth"],
    summary="네이버 소셜 로그인",
    description="네이버 OAuth 인가 코드(code)와 state로 로그인 또는 회원가입을 처리합니다.",
    request=NaverAuthRequestSerializer,
    responses={
        200: SocialAuthResponseSerializer,
        400: OpenApiResponse(description="요청 형식이 올바르지 않습니다."),
        401: OpenApiResponse(description="유효하지 않은 네이버 토큰입니다."),
        403: OpenApiResponse(description="네이버 접근 권한이 없습니다."),
    },
)
class NaverAuthView(BaseSocialAuthView):
    provider = "naver"
    provider_label = "네이버"

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = NaverAuthRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code: str = serializer.validated_data["code"]
        state: Optional[str] = serializer.validated_data.get("state")

        result = SocialAuthService.handle_social_login(self.provider, code, state)
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
