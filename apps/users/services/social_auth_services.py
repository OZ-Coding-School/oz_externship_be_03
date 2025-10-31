from typing import Any

import requests
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken
from requests.exceptions import RequestException

from apps.users.models import SocialUser, User


class SocialAuthService:
    """소셜 로그인 처리 서비스"""

    # -------------------------------------
    # 1️⃣ Provider별 사용자 정보 조회
    # -------------------------------------
    @staticmethod
    def get_user_info(provider: str, data: dict[str, Any]) -> dict[str, Any]:
        access_token = data.get("access_token")
        if not access_token:
            raise ValueError("access_token이 필요합니다.")

        try:
            if provider == "kakao":
                headers = {"Authorization": f"Bearer {access_token}"}
                response = requests.get("https://kapi.kakao.com/v2/user/me", headers=headers)
                response.raise_for_status()
                kakao_data = response.json()
                account = kakao_data.get("kakao_account", {})
                return {
                    "email": account.get("email"),
                    "name": account.get("profile", {}).get("nickname", ""),
                    "provider": "kakao",
                    "provider_id": kakao_data.get("id"),
                }

            elif provider == "naver":
                headers = {"Authorization": f"Bearer {access_token}"}
                response = requests.get("https://openapi.naver.com/v1/nid/me", headers=headers)
                response.raise_for_status()
                naver_data = response.json().get("response", {})
                return {
                    "email": naver_data.get("email"),
                    "name": naver_data.get("name"),
                    "provider": "naver",
                    "provider_id": naver_data.get("id"),
                }

            else:
                raise ValueError("지원하지 않는 provider입니다.")

        except RequestException:
            raise ValueError(f"{provider} 사용자 정보 요청 중 오류가 발생했습니다.")
        except KeyError:
            raise ValueError(f"{provider} 사용자 정보 파싱에 실패했습니다.")

    # -------------------------------------
    # 2️⃣ 메인 소셜 로그인 로직
    # -------------------------------------
    @staticmethod
    def social_login(provider: str, data: dict[str, Any]) -> dict[str, Any]:
        """소셜 로그인 메인 로직"""

        # 1. Provider별 사용자 정보 조회
        user_info = SocialAuthService.get_user_info(provider, data)
        email = user_info.get("email")
        if not email:
            raise ValueError("소셜 계정에서 이메일을 가져올 수 없습니다.")

        # 2. 유저 생성 or 조회
        user, _ = User.objects.get_or_create(
            email=email,
            defaults={
                "name": user_info.get("name", ""),
                "is_active": True,
            },
        )

        # 3. 소셜 계정 연결 (있으면 provider_id 업데이트)
        social_user, created = SocialUser.objects.get_or_create(
            user=user,
            provider=user_info["provider"],
            defaults={"provider_id": user_info["provider_id"]},
        )
        if not created and social_user.provider_id != user_info["provider_id"]:
            social_user.provider_id = user_info["provider_id"]
            social_user.save(update_fields=["provider_id"])

        # 4. JWT 발급
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        access_expire_seconds = int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds())  # type: ignore

        # 5. 응답 구조 (Serializer와 1:1 매칭)
        return {
            "detail": f"{provider.capitalize()} 로그인에 성공했습니다.",
            "result": {
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "name": user.name,
                    "nickname": getattr(user, "nickname", None),
                    "provider": social_user.provider,
                },
                "access_token": access_token,
                "token_type": "Bearer",
                "access_token_expires_in": access_expire_seconds,
            },
        }
