from typing import Any, Dict

import requests
from django.conf import settings
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
)
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.services.social_auth_services import SocialAuthService

# from __future__ import annotations


class SocialAuthView(APIView):

    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Auth"],
        summary="소셜 로그인 (카카오 / 네이버)",
        description=(
            "프론트엔드에서 인가 코드(code)를 전달하면 서버가 Access Token을 발급받고, "
            "유저 정보를 조회하여 자동 회원가입 또는 로그인을 수행합니다.\n\n"
            "- provider: kakao 또는 naver\n"
            "- 요청 body에는 `code` 필수, `state`(naver만 해당) 선택입니다."
        ),
        parameters=[
            OpenApiParameter(
                name="provider",
                location=OpenApiParameter.PATH,
                required=True,
                description="소셜 로그인 제공자 (kakao 또는 naver)",
                examples=[
                    OpenApiExample(name="kakao", value="kakao", summary="카카오 로그인"),
                    OpenApiExample(name="naver", value="naver", summary="네이버 로그인"),
                ],
            ),
        ],
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "example": "4/0Ad..."},
                    "state": {"type": "string", "example": "RANDOM_STATE_STRING"},
                },
                "required": ["code"],
            }
        },
        responses={
            200: OpenApiResponse(
                description="로그인 성공 시 JWT 발급 및 사용자 정보 반환",
                examples=[
                    OpenApiExample(
                        name="성공 예시",
                        summary="소셜 로그인 성공",
                        value={
                            "detail": "Kakao 로그인에 성공했습니다.",
                            "result": {
                                "user": {
                                    "id": 1,
                                    "email": "user@example.com",
                                    "name": "홍길동",
                                    "nickname": "길동이",
                                    "provider": "kakao",
                                },
                                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                                "token_type": "Bearer",
                                "access_token_expires_in": 3600,
                            },
                        },
                    )
                ],
            ),
        },
    )
    def post(self, request: Request, provider: str) -> Response:
        # 유효성 검증
        if provider not in ("kakao", "naver"):
            return Response(
                {"detail": "지원하지 않는 provider입니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        code: str | None = request.data.get("code")
        state: str | None = request.data.get("state")

        if not code:
            raise serializers.ValidationError({"code": "인가 코드(code)가 필요합니다."})

        # Access Token 요청
        try:
            token_url: str
            payload: Dict[str, Any]

            if provider == "kakao":
                token_url = "https://kauth.kakao.com/oauth/token"
                payload = {
                    "grant_type": "authorization_code",
                    "client_id": settings.KAKAO_CLIENT_ID,
                    "redirect_uri": settings.KAKAO_REDIRECT_URI,
                    "code": code,
                }

            elif provider == "naver":
                token_url = "https://nid.naver.com/oauth2.0/token"
                payload = {
                    "grant_type": "authorization_code",
                    "client_id": settings.NAVER_CLIENT_ID,
                    "client_secret": settings.NAVER_CLIENT_SECRET,
                    "code": code,
                    "state": state,
                }

            response: requests.Response = requests.post(token_url, data=payload)
            response.raise_for_status()
            access_token: str | None = response.json().get("access_token")

        except requests.RequestException:
            return Response(
                {"detail": f"{provider} access_token 요청 실패"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not access_token:
            return Response(
                {"detail": f"{provider} access_token을 가져오지 못했습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 서비스 호출
        try:
            result: Dict[str, Any] = SocialAuthService.social_login(provider, {"access_token": access_token})
            return Response(result, status=status.HTTP_200_OK)

        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
