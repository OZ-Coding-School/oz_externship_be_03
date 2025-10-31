import requests
from django.conf import settings
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.services.social_auth_services import SocialAuthService


class SocialAuthView(APIView):
    """
    카카오/네이버 소셜 로그인 뷰 (인가 코드 기반)
    """

    def post(self, request, provider: str):
        # -----------------------------
        # 1️⃣ provider 유효성 검증
        # -----------------------------
        if provider not in ["kakao", "naver"]:
            return Response({"detail": "지원하지 않는 provider입니다."}, status=status.HTTP_400_BAD_REQUEST)

        code = request.data.get("code")
        state = request.data.get("state")

        if not code:
            raise serializers.ValidationError({"code": "인가 코드(code)가 필요합니다."})

        # -----------------------------
        # 2️⃣ provider별 Access Token 요청
        # -----------------------------
        access_token = None

        try:
            if provider == "kakao":
                kakao_token_url = "https://kauth.kakao.com/oauth/token"
                payload = {
                    "grant_type": "authorization_code",
                    "client_id": settings.KAKAO_CLIENT_ID,
                    "redirect_uri": settings.KAKAO_REDIRECT_URI,
                    "code": code,
                }

                response = requests.post(kakao_token_url, data=payload)
                response.raise_for_status()
                access_token = response.json().get("access_token")

            elif provider == "naver":
                naver_token_url = "https://nid.naver.com/oauth2.0/token"
                payload = {
                    "grant_type": "authorization_code",
                    "client_id": settings.NAVER_CLIENT_ID,
                    "client_secret": settings.NAVER_CLIENT_SECRET,
                    "code": code,
                    "state": state,
                }

                response = requests.post(naver_token_url, data=payload)
                response.raise_for_status()
                access_token = response.json().get("access_token")

        except requests.RequestException:
            return Response({"detail": f"{provider} 토큰 요청 실패"}, status=status.HTTP_400_BAD_REQUEST)

        if not access_token:
            return Response(
                {"detail": f"{provider} access_token을 가져오지 못했습니다."}, status=status.HTTP_400_BAD_REQUEST
            )

        # -----------------------------
        # 3️⃣ 통합 소셜 로그인 로직 호출
        # -----------------------------
        try:
            result = SocialAuthService.social_login(provider, {"access_token": access_token})
            return Response(result, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
