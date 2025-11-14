from __future__ import annotations

from typing import Any

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.serializers.social_auth_serializers import (
    KakaoAuthRequestSerializer,
    KakaoSocialResponseSerializer,
    NaverSocialRequestSerializer,
    NaverSocialResponseSerializer,
)
from apps.users.services.social_auth_services import KakaoAuthService, NaverAuthService
from apps.users.utils.cookies import set_refresh_cookie


# 공통
def _extract_access_token(result: dict[str, Any]) -> str:
    return result.get("data", {}).get("access") or result.get("data", {}).get("access_token") or "mock_access_token"


# 카카오
@extend_schema(
    tags=["Auth"],
    summary="카카오 로그인",
    request=KakaoAuthRequestSerializer,
    responses={
        200: KakaoSocialResponseSerializer,
        400: OpenApiResponse(description="요청 형식이 올바르지 않습니다."),
        401: OpenApiResponse(description="유효하지 않은 카카오 토큰입니다."),
        500: OpenApiResponse(description="서버 내부 오류"),
    },
)
class KakaoAuthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: tuple[Any, ...] = ()

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = KakaoAuthRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        code = serializer.validated_data["code"]

        try:
            result = KakaoAuthService().handle_login(code)
            response_data = {
                "detail": result.get("detail", "카카오 로그인이 완료되었습니다."),
                "data": {
                    "access_token": result.get("data", {}).get("access"),
                },
            }

            response_serializer = KakaoSocialResponseSerializer(data=response_data)
            response_serializer.is_valid(raise_exception=True)

            response = Response(response_serializer.data, status=status.HTTP_200_OK)
            refresh_token = result.get("data", {}).get("refresh")
            if refresh_token:
                set_refresh_cookie(response, refresh_token)

            return response

        except ValidationError as e:
            error_msg = str(e)
            if "다른 소셜" in error_msg:
                return Response(
                    {"error": "이미 다른 소셜 계정과 연결되어 있습니다. 연결된 소셜 계정으로 로그인해주세요."},
                    status=400,
                )
            if any(k in error_msg for k in ["토큰", "access"]):
                return Response({"error": "유효하지 않은 카카오 토큰입니다."}, status=401)

            if any(k in error_msg for k in ["code", "인가"]):
                return Response({"error": "인가 코드가 유효하지 않습니다."}, status=400)

            return Response(
                {"error": "요청 형식이 올바르지 않습니다."},
                status=400,
            )
        except PermissionError:
            return Response(
                {"error": "잘못된 접근입니다. 요청이 위조되었을 수 있습니다."},
                status=403,
            )
        except Exception as e:
            print(f"[KakaoAuthView] Unhandled exception: {e}")
            return Response({"error": "예상치 못한 서버 오류가 발생했습니다."}, status=500)


# 네이버
@extend_schema(
    tags=["Auth"],
    summary="네이버 로그인",
    request=NaverSocialRequestSerializer,
    responses={
        200: NaverSocialResponseSerializer,
        400: OpenApiResponse(description="요청 형식이 올바르지 않습니다."),
        401: OpenApiResponse(description="유효하지 않은 네이버 토큰입니다."),
        403: OpenApiResponse(description="잘못된 접근입니다."),
        500: OpenApiResponse(description="서버 내부 오류"),
    },
)
class NaverAuthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: tuple[Any, ...] = ()

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = NaverSocialRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        code = validated_data.get("code")
        state = validated_data.get("state")

        try:
            result = NaverAuthService.handle_login(code, state)
            response_data = {
                "detail": result.get("detail", "네이버 로그인이 완료되었습니다."),
                "data": {
                    "access_token": result.get("data", {}).get("access"),
                },
            }

            response_serializer = NaverSocialResponseSerializer(data=response_data)
            response_serializer.is_valid(raise_exception=True)

            response = Response(response_serializer.data, status=status.HTTP_200_OK)
            refresh_token = result.get("data", {}).get("refresh")
            if refresh_token:
                set_refresh_cookie(response, refresh_token)

            return response

        except ValidationError as e:
            error_msg = str(e)
            if "다른 소셜" in error_msg:
                return Response(
                    {"error": "이미 다른 소셜 계정과 연결되어 있습니다. 연결된 소셜 계정으로 로그인해주세요."},
                    status=400,
                )
            if any(k in error_msg for k in ["토큰", "access"]):
                return Response({"error": "유효하지 않은 카카오 토큰입니다."}, status=401)
            if any(k in error_msg for k in ["code", "인가"]):
                return Response({"error": "인가 코드가 유효하지 않습니다."}, status=400)
            return Response(
                {"error": "요청 형식이 올바르지 않습니다."},
                status=400,
            )

        except PermissionError:
            return Response(
                {"error": "잘못된 접근입니다. 요청이 위조되었을 수 있습니다."},
                status=403,
            )
        except Exception as e:
            print(f"[KakaoAuthView] Unhandled exception: {e}")
            return Response({"error": "예상치 못한 서버 오류가 발생했습니다."}, status=500)
