from __future__ import annotations

from typing import Any, Dict, Optional, cast

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email as django_validate_email
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import (
    ExpiredTokenError,
    InvalidToken,
    TokenError,
)
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.views import ExceptionHandledAPIView
from apps.users.models.user import User
from apps.users.serializers.auth_serializers import (
    LoginRequestSerializer,
    LoginResponseSerializer,
    TokenRefreshResponseSerializer,
)
from apps.users.services.auth_services import (
    authenticate_and_issue_tokens,
    refresh_access_token,
)
from apps.users.utils.cookies import set_refresh_cookie
from apps.users.utils.jwt import extract_bearer_token, is_jwt_like


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

    if password != password.strip():
        raise serializers.ValidationError({"password": ["비밀번호 앞뒤 공백은 허용되지 않습니다."]})

    email_str = User.objects.normalize_email(email)

    try:
        django_validate_email(email_str)
    except DjangoValidationError:
        raise serializers.ValidationError({"email": ["이메일 형식이 올바르지 않습니다."]})

    local, _, domain = email.strip().partition("@")
    payload["email"] = f"{local}@{domain.lower()}"


# ---------------------------------------------------------------------
# 뷰: 로그인
# ---------------------------------------------------------------------
class LoginView(APIView):
    """
    로그인 뷰
    POST /auth/login
    body: { "email": "...", "password": "..." }
    """

    authentication_classes: tuple[type[BaseAuthentication], ...] = ()
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Auth"],
        summary="로그인",
        description=(
            "access/refresh 토큰을 발급\n" f"- refresh 토큰은 ** 쿠키(`{settings.AUTH_REFRESH_COOKIE_NAME}`)**에 저장\n"
        ),
        request=LoginRequestSerializer,
        responses={201: LoginResponseSerializer},
    )
    def post(self, request: Request) -> Response:
        # 1) 스키마 체크
        in_ser = LoginRequestSerializer(data=request.data)
        in_ser.is_valid(raise_exception=True)
        payload: Dict[str, Any] = dict(in_ser.validated_data)

        # 2) validator
        _validate_login_payload(payload)

        # 3) 서비스 호출
        try:
            tokens = authenticate_and_issue_tokens(
                email=payload["email"],
                password=payload["password"],
            )
        except PermissionError:
            return Response(
                {"error": "이메일 또는 비밀번호가 올바르지 않습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 4) 응답 및 리프레시 쿠키 저장
        out_ser = LoginResponseSerializer(data={"access": tokens["access"]})
        out_ser.is_valid(raise_exception=True)

        resp = Response(
            {"detail": "토큰이 발급되었습니다.", "data": out_ser.data},
            status=status.HTTP_201_CREATED,
        )
        set_refresh_cookie(resp, tokens["refresh"])
        return resp


# ---------------------------------------------------------------------
# 뷰: 액세스 토큰 재발급
# ---------------------------------------------------------------------
class TokenRefreshView(APIView):
    """
    액세스 토큰 재발급 뷰
    POST /auth/refresh
    """

    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Auth"],
        summary="access 토큰 재발급",
        description=(
            "리프레시 토큰은 **HttpOnly 쿠키**에서 읽어 재발급\n" f"- 쿠키 키: `{settings.AUTH_REFRESH_COOKIE_NAME}`\n"
        ),
        parameters=[
            OpenApiParameter(
                name=settings.AUTH_REFRESH_COOKIE_NAME,
                location=OpenApiParameter.COOKIE,
                required=True,
                description="리프레시 토큰이 저장된 HttpOnly 쿠키",
            ),
        ],
        request=None,
        responses={200: TokenRefreshResponseSerializer},
    )
    def post(self, request: Request) -> Response:
        # 1) 쿠키에서만 리프레시 토큰 획득
        refresh_token_value: Optional[str] = request.COOKIES.get(settings.AUTH_REFRESH_COOKIE_NAME)
        if not refresh_token_value:
            return Response(
                {"error": "리프레시 토큰이 필요합니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2) 형식 검사(JWT-like)
        if not is_jwt_like(refresh_token_value):
            return Response(
                {"error": "refresh 토큰 형식이 올바르지 않습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            new_access = refresh_access_token(refresh_token=refresh_token_value)
        except PermissionError:
            return Response(
                {"error": "유효하지 않은 리프레시 토큰입니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        out_ser = TokenRefreshResponseSerializer(data={"access": new_access})
        out_ser.is_valid(raise_exception=True)
        return Response(
            {"detail": "액세스 토큰이 재발급되었습니다.", "data": out_ser.data},
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------
# 뷰: 로그아웃
# ---------------------------------------------------------------------
class LogoutView(ExceptionHandledAPIView):
    """
    로그아웃: refresh/access 즉시 무효화(캐시 denylist) + 쿠키 삭제
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Auth"],
        summary="로그아웃",
        description=("쿠키의 refresh를 캐시 denylist로 무효화하고 삭제"),
        request=None,
        responses={200: {"type": "object", "properties": {"detail": {"type": "string"}}}},
    )
    def post(self, request: Request) -> Response:
        refresh_raw = request.COOKIES.get(settings.AUTH_REFRESH_COOKIE_NAME)
        access_token = extract_bearer_token(request)

        if not refresh_raw or not access_token:
            raise AuthenticationFailed("로그인된 상태가 아닙니다.")

        refresh_token = RefreshToken(cast(Any, refresh_raw))

        try:
            refresh_token.blacklist()
        except InvalidToken:
            return Response({"error": "유효하지 않은 토큰입니다."}, status=401)
        except ExpiredTokenError:
            return Response({"error": "토큰이 만료되었습니다."}, status=401)
        except TokenError:
            # 이미 블랙리스트에 있을 경우 성공 처리
            return Response({"detail": "이미 로그아웃된 유저입니다."}, status=200)

        resp = Response({"detail": "로그아웃이 완료되었습니다."}, status=200)
        resp.delete_cookie(settings.AUTH_REFRESH_COOKIE_NAME)
        return resp
