from __future__ import annotations

from typing import Any, Dict, Optional

import requests
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

from apps.users.enums import Provider
from apps.users.serializers.social_auth_serializers import SocialAuthRequestSerializer
from apps.users.services.social_auth_services import SocialAuthService


class SocialAuthView(APIView):
    """
    소셜 로그인 (카카오 / 네이버)

    프론트엔드에서 인가 코드(code)를 전달하면,
    서버가 Access Token을 발급받고 사용자 정보를 가져와 자동 회원가입 또는 로그인을 수행합니다.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Auth"],
        summary="소셜 로그인 (카카오 / 네이버)",
        request=SocialAuthRequestSerializer,
        parameters=[
            OpenApiParameter(
                name="provider",
                location=OpenApiParameter.PATH,
                required=True,
                description="소셜 로그인 제공자",
                examples=[
                    OpenApiExample(name="kakao", value=Provider.KAKAO.value, summary="카카오 로그인"),
                    OpenApiExample(name="naver", value=Provider.NAVER.value, summary="네이버 로그인"),
                ],
            ),
        ],
        responses={
            200: OpenApiResponse(
                description="로그인 성공 시",
                examples=[
                    OpenApiExample(
                        name="성공 예시",
                        value={"detail": "Kakao 로그인에 성공했습니다."},
                    )
                ],
            ),
            400: OpenApiResponse(
                description="요청 형식 오류 / 토큰 발급 실패 / 서버 오류",
                examples=[
                    OpenApiExample(
                        name="형식 오류",
                        value={"error": "요청 형식이 올바르지 않습니다. code는 필수값입니다."},
                    ),
                    OpenApiExample(
                        name="토큰 오류",
                        value={"error": "Kakao 로그인 처리 중 오류가 발생했습니다."},
                    ),
                ],
            ),
            401: OpenApiResponse(
                description="인증 실패 (잘못된 토큰)",
                examples=[
                    OpenApiExample(
                        name="인증 오류",
                        value={"error": "유효하지 않은 카카오 토큰입니다. 다시 로그인해주세요."},
                    ),
                ],
            ),
            403: OpenApiResponse(
                description="권한 거부 (위조 요청 등)",
                examples=[
                    OpenApiExample(
                        name="권한 오류",
                        value={"error": "잘못된 접근입니다. 요청이 위조되었을 수 있습니다."},
                    ),
                ],
            ),
        },
    )
    def post(self, request: Request, provider: Optional[str] = None, *args: Any, **kwargs: Any) -> Response:
        """소셜 로그인 처리 (카카오 / 네이버 / 구글)"""

        provider = provider or kwargs.get("provider")

        # ✅ Enum 기반 provider 검증
        if provider not in Provider.values:
            return Response(
                {"error": "지원하지 않는 provider입니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SocialAuthRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data["code"]

        try:
            result: Dict[str, Any] = SocialAuthService.social_login(provider, code)
            provider_label = Provider(provider).label  # Enum label (예: "Kakao")
            return Response(
                {"detail": f"{provider_label} 로그인에 성공했습니다.", **result},
                status=status.HTTP_200_OK,
            )

        except requests.RequestException:
            return Response(
                {"error": f"{Provider(provider).label} 서버 통신 중 오류가 발생했습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except serializers.ValidationError:
            return Response(
                {"error": f"{Provider(provider).label} 로그인 검증에 실패했습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except PermissionError:
            return Response(
                {"error": "잘못된 접근입니다. 요청이 위조되었을 수 있습니다."},
                status=status.HTTP_403_FORBIDDEN,
            )

        except Exception:
            return Response(
                {"error": f"{Provider(provider).label} 로그인 처리 중 오류가 발생했습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )
