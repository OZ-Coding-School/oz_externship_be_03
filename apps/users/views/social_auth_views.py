from __future__ import annotations

from typing import Any, Dict, Optional

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


class SocialAuthView(APIView):
    """카카오 / 네이버 소셜 로그인 뷰"""

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
                description="로그인 성공 시 성공 메시지 반환",
                examples=[
                    OpenApiExample(
                        name="성공 예시",
                        value={
                            "detail": "Kakao 로그인에 성공했습니다.",
                        },
                    )
                ],
            ),
            400: OpenApiResponse(
                description="오류 발생 시",
                examples=[
                    OpenApiExample(
                        name="에러 예시",
                        value={"detail": "Kakao 로그인 실패: access_token이 필요합니다."},
                    )
                ],
            ),
        },
    )
    def post(self, request: Request, provider: Optional[str] = None, *args: Any, **kwargs: Any) -> Response:

        provider = provider or kwargs.get("provider")

        # ✅ provider 검증
        if provider not in ("kakao", "naver"):
            return Response(
                {"detail": "지원하지 않는 provider입니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ✅ code 유효성 검증
        code: Optional[str] = request.data.get("code")
        if not code:
            raise serializers.ValidationError({"code": "인가 코드(code)가 필요합니다."})

        # ✅ Access token 요청 및 사용자 정보 처리
        try:
            result: Dict[str, Any] = SocialAuthService.social_login(provider, code)
            return Response(result, status=status.HTTP_200_OK)

        except requests.RequestException as e:
            # 외부 API 통신 에러 (카카오/네이버 서버 문제)
            return Response(
                {"detail": f"{provider.capitalize()} 서버 통신 중 오류: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except serializers.ValidationError as e:
            # 사용자 데이터 검증 오류
            return Response(
                {"detail": f"{provider.capitalize()} 로그인 검증 실패: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception as e:
            # 그 외 모든 예외
            return Response(
                {"detail": f"{provider.capitalize()} 로그인 실패: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
