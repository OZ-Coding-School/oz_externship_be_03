from __future__ import annotations

from typing import Any, Dict, Literal, Optional, cast

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email as django_validate_email
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.serializers.auth_serializers import (
    LoginSerializer,
    TokenObtainOutSerializer,
    TokenRefreshInSerializer,
    TokenRefreshOutSerializer,
)
from apps.users.services.auth_token_services import (
    authenticate_and_issue_tokens,
    refresh_access_token,
)
from config.settings.base import (
    AUTH_REFRESH_COOKIE_HTTPONLY,
    AUTH_REFRESH_COOKIE_MAX_AGE,
    AUTH_REFRESH_COOKIE_NAME,
    AUTH_REFRESH_COOKIE_PATH,
    AUTH_REFRESH_COOKIE_SAMESITE,
    AUTH_REFRESH_COOKIE_SECURE,
)

SameSite = Optional[Literal["Lax", "Strict", "None", False]]
COOKIE_SAMESITE: SameSite = cast(SameSite, AUTH_REFRESH_COOKIE_SAMESITE)


def _set_refresh_cookie(resp: Response, refresh: str) -> None:

    resp.set_cookie(
        key=AUTH_REFRESH_COOKIE_NAME,
        value=refresh,
        max_age=AUTH_REFRESH_COOKIE_MAX_AGE,
        path=AUTH_REFRESH_COOKIE_PATH,
        secure=AUTH_REFRESH_COOKIE_SECURE,
        httponly=AUTH_REFRESH_COOKIE_HTTPONLY,
        samesite=COOKIE_SAMESITE,
    )


# TODO: 만료/로그아웃 시 쿠키 삭제 함수
def _pop_refresh_cookie(resp: Response) -> None:
    resp.delete_cookie(
        key=AUTH_REFRESH_COOKIE_NAME,
        path=AUTH_REFRESH_COOKIE_PATH,
        samesite=COOKIE_SAMESITE,
    )


# ==============================
# 유효성 검증
# ==============================
def _validate_login_payload(payload: Dict[str, Any]) -> None:
    email = payload.get("email")
    password = payload.get("password")

    if not isinstance(email, str) or not email.strip():
        raise serializers.ValidationError({"email": ["이메일을 입력해주세요."]})
    if not isinstance(password, str) or not password:
        raise serializers.ValidationError({"password": ["비밀번호를 입력해주세요."]})

    try:
        django_validate_email(email)
    except DjangoValidationError:
        raise serializers.ValidationError({"email": ["이메일 형식이 올바르지 않습니다."]})

    local, _, domain = email.strip().partition("@")
    payload["email"] = f"{local}@{domain.lower()}"


def _is_jwt_like(token: str) -> bool:
    parts = token.split(".")
    return len(parts) == 3 and all(p for p in parts)


def _validate_refresh_payload(payload: Dict[str, Any]) -> None:
    refresh = payload.get("refresh")
    if not isinstance(refresh, str) or not refresh.strip():
        raise serializers.ValidationError({"refresh": ["refresh 토큰을 입력해주세요."]})
    if not _is_jwt_like(refresh):
        raise serializers.ValidationError({"refresh": ["refresh 토큰 형식이 올바르지 않습니다."]})
    payload["refresh"] = refresh.strip()


# ==============================
# 뷰
# ==============================
class TokenObtainView(APIView):
    """
    POST /auth/login
    body: { "email": "...", "password": "..." }
    """

    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Auth"],
        summary="로그인",
        description=(
            "access/refresh 토큰을 발급\n" f"- refresh 토큰은 ** 쿠키(`{AUTH_REFRESH_COOKIE_NAME}`)**에 저장\n"
        ),
        request=LoginSerializer,
        responses={200: TokenObtainOutSerializer},
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        # 1) 스키마 체크
        in_ser = LoginSerializer(data=request.data)
        in_ser.is_valid(raise_exception=True)
        payload: Dict[str, Any] = dict(in_ser.validated_data)

        # 2) validator
        _validate_login_payload(payload)

        # 3) 서비스 호출
        try:
            user, tokens = authenticate_and_issue_tokens(
                email=payload["email"],
                password=payload["password"],
            )
        except PermissionError:
            return Response(
                {"error": "이메일 또는 비밀번호가 올바르지 않습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 4) 응답 및 리프레시 쿠키 저장
        out_ser = TokenObtainOutSerializer(
            data={
                "user": {
                    "email": getattr(user, "email"),
                    "nickname": getattr(user, "nickname"),
                },
                "access": tokens["access"],
            }
        )
        out_ser.is_valid(raise_exception=True)

        resp = Response(
            {"detail": "토큰이 발급되었습니다.", "data": out_ser.data},
            status=status.HTTP_200_OK,
        )
        _set_refresh_cookie(resp, tokens["refresh"])
        return resp


class TokenRefreshView(APIView):
    """
    POST /auth/refresh
    body (선택): { "refresh": "<refresh_token>" }
    """

    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Auth"],
        summary="access 토큰 재발급",
        description=(
            "리프레시 토큰은 **HttpOnly 쿠키**에서 읽어 재발급\n"
            f"- 쿠키 키: `{AUTH_REFRESH_COOKIE_NAME}`\n"
            "- 만약 쿠키가 없다면, 요청 본문 `refresh` 필드 참조"
        ),
        parameters=[
            OpenApiParameter(
                name=AUTH_REFRESH_COOKIE_NAME,
                location=OpenApiParameter.COOKIE,
                required=False,
                description="리프레시 토큰이 저장된 HttpOnly 쿠키",
            ),
        ],
        request=TokenRefreshInSerializer,
        responses={200: TokenRefreshOutSerializer},
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        # 1) 쿠키에서 리프레시 토큰 획득
        cookie_refresh = request.COOKIES.get(AUTH_REFRESH_COOKIE_NAME)

        # 2) 쿠키가 없으면 본문에서 획득
        body_refresh: Optional[str] = None
        if not cookie_refresh:
            in_ser = TokenRefreshInSerializer(data=request.data)
            in_ser.is_valid(raise_exception=True)
            payload: Dict[str, Any] = dict(in_ser.validated_data)
            _validate_refresh_payload(payload)
            body_refresh = payload["refresh"]

        refresh_token_value = cookie_refresh or body_refresh
        if not refresh_token_value:
            return Response(
                {"error": "리프레시 토큰이 필요합니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            new_access = refresh_access_token(refresh_token=refresh_token_value)
        except PermissionError:
            return Response(
                {"error": "유효하지 않은 refresh 토큰입니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        out_ser = TokenRefreshOutSerializer(data={"access": new_access})
        out_ser.is_valid(raise_exception=True)
        return Response(
            {"detail": "access 토큰이 재발급되었습니다.", "data": out_ser.data},
            status=status.HTTP_200_OK,
        )
