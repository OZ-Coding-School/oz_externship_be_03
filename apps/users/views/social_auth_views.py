from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
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
    request=SocialAuthRequestSerializer,
    responses={
        200: SocialAuthResponseSerializer,
        400: OpenApiResponse(description="요청 형식이 올바르지 않거나 인가 코드가 유효하지 않습니다."),
        401: OpenApiResponse(description="유효하지 않은 토큰입니다."),
        403: OpenApiResponse(description="잘못된 접근입니다."),
        500: OpenApiResponse(description="서버 내부 오류"),
    },
)
class SocialAuthView(APIView):

    permission_classes = [AllowAny]
    authentication_classes: tuple[Any, ...] = ()

    def post(self, request: Request, provider: str, *args: Any, **kwargs: Any) -> Response:

        serializer = SocialAuthRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error": "요청 형식이 올바르지 않습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        code = serializer.validated_data["code"]
        state = serializer.validated_data.get("state")
        try:
            # 회원가입
            result = SocialAuthService.handle_social_login(provider, code, state)
            data = {
                "detail": result.get("detail", f"{provider.capitalize()} 로그인에 성공했습니다."),
                "data": {
                    "access_token": result.get("data", {}).get("access"),
                },
            }

            response = Response(data, status=status.HTTP_200_OK)

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

        except ValidationError as e:
            error_msg = str(e)
            provider_name = "카카오" if provider == "kakao" else "네이버"

            if "토큰" in error_msg or "access" in error_msg:
                return Response(
                    {"error": f"유효하지 않은 {provider_name} 토큰입니다. 다시 로그인해주세요."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            if "code" in error_msg or "인가" in error_msg:
                return Response(
                    {"error": f"{provider_name} 인가 코드가 유효하지 않습니다."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return Response(
                {"error": "요청 형식이 올바르지 않습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except PermissionError:
            return Response(
                {"error": "잘못된 접근입니다. 요청이 위조되었을 수 있습니다."},
                status=status.HTTP_403_FORBIDDEN,
            )

        except Exception as e:
            print(f"[SocialAuthView] Unhandled exception: {e}")
            return Response(
                {"error": "예상하지 못한 에러가 발생했습니다."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
