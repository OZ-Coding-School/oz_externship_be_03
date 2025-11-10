from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.serializers.social_auth_serializers import (
    KakaoAuthRequestSerializer,
    NaverSocialRequestSerializer,
    SocialAuthResponseSerializer,
)
from apps.users.services.social_auth_services import KakaoAuthService, NaverAuthService


# 카카오
@extend_schema(
    tags=["Auth"],
    summary="카카오 로그인",
    description="카카오 인가 코드(code)를 이용해 로그인 또는 회원가입을 처리합니다.",
    request=KakaoAuthRequestSerializer,
    examples=[
        OpenApiExample(
            "Kakao Example",
            summary="카카오 로그인 요청 예시",
            value={"code": "FAKE_KAKAO_CODE"},
        ),
    ],
    responses={
        200: SocialAuthResponseSerializer,
        400: OpenApiResponse(description="요청 형식이 올바르지 않거나 인가 코드가 유효하지 않습니다."),
        401: OpenApiResponse(description="유효하지 않은 카카오 토큰입니다."),
        500: OpenApiResponse(description="서버 내부 오류"),
    },
)
class KakaoAuthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: tuple[Any, ...] = ()

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = KakaoAuthRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error": "요청 형식이 올바르지 않습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        code = serializer.validated_data["code"]

        try:
            result = KakaoAuthService.handle_login(code)
            data = {
                "detail": result.get("detail", "카카오 로그인에 성공했습니다."),
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
            if "토큰" in error_msg or "access" in error_msg:
                return Response(
                    {"error": "유효하지 않은 카카오 토큰입니다. 다시 로그인해주세요."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            if "code" in error_msg or "인가" in error_msg:
                return Response(
                    {"error": "카카오 인가 코드가 유효하지 않습니다."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return Response(
                {"error": "요청 형식이 올바르지 않습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception as e:
            print(f"[KakaoAuthView] Unhandled exception: {e}")
            return Response(
                {"error": "예상하지 못한 에러가 발생했습니다."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# 네이버
@extend_schema(
    tags=["Auth"],
    summary="네이버 로그인",
    description="네이버 인가 코드(code)와 state를 이용해 로그인 또는 회원가입을 처리합니다.",
    request=NaverSocialRequestSerializer,
    examples=[
        OpenApiExample(
            "Naver Example",
            summary="네이버 로그인 요청 예시",
            value={"code": "FAKE_NAVER_CODE", "state": "FAKE_STATE"},
        ),
    ],
    responses={
        200: SocialAuthResponseSerializer,
        400: OpenApiResponse(description="요청 형식이 올바르지 않거나 인가 코드가 유효하지 않습니다."),
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
        if not serializer.is_valid():
            return Response(
                {"error": "요청 형식이 올바르지 않습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        code = serializer.validated_data["code"]
        state = serializer.validated_data["state"]

        try:
            result = NaverAuthService.handle_login(code, state)
            data = {
                "detail": result.get("detail", "네이버 로그인에 성공했습니다."),
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
            if "토큰" in error_msg or "access" in error_msg:
                return Response(
                    {"error": "유효하지 않은 네이버 토큰입니다. 다시 로그인해주세요."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            if "code" in error_msg or "인가" in error_msg:
                return Response(
                    {"error": "네이버 인가 코드가 유효하지 않습니다."},
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
            print(f"[NaverAuthView] Unhandled exception: {e}")
            return Response(
                {"error": "예상하지 못한 에러가 발생했습니다."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
