from typing import Any, Optional

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.enums import Provider
from apps.users.serializers.social_auth_serializers import SocialAuthRequestSerializer
from apps.users.services.social_auth_services import SocialAuthService


class SocialAuthView(APIView):

    permission_classes = [AllowAny]

    def post(
        self,
        request: Request,
        provider: Optional[str] = None,
        *args: Any,
        **kwargs: Any,
    ) -> Response:
        provider = provider or kwargs.get("provider")

        if provider not in [Provider.KAKAO.value, Provider.NAVER.value]:
            return Response(
                {"error": f"지원하지 않는 provider입니다: {provider}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SocialAuthRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data["code"]

        try:
            result = SocialAuthService.handle_social_login(provider, code)
            access_token = result.get("access")
            refresh_token = result.get("refresh")

            response = Response(
                {
                    "detail": result.get("detail", f"{provider} 로그인에 성공했습니다."),
                    "access": access_token,
                },
                status=status.HTTP_200_OK,
            )

            if refresh_token:
                response.set_cookie(
                    key=settings.AUTH_REFRESH_COOKIE_NAME,
                    value=refresh_token,
                    httponly=True,
                    samesite="Lax",
                    secure=False,
                )

            return response

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
