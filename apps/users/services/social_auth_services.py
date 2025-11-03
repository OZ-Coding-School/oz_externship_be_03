from __future__ import annotations

from typing import Any

import requests
from django.conf import settings
from django.core.exceptions import ValidationError
from requests.exceptions import RequestException

from apps.users.models import SocialUser, User
from apps.users.services.auth_services import _issue_tokens


class SocialAuthService:

    # kakao/naver 사용자 정보 조회
    @staticmethod
    def get_user_info(provider: str, data: dict[str, Any]) -> dict[str, Any]:
        access_token = data.get("access_token")
        if not access_token:
            raise ValidationError("access_token이 필요합니다.")

        try:
            if provider == "kakao":
                headers = {"Authorization": f"Bearer {access_token}"}
                response = requests.get("https://kapi.kakao.com/v2/user/me", headers=headers)
                response.raise_for_status()
                kakao_data = response.json()
                account = kakao_data.get("kakao_account", {})
                profile = account.get("profile", {})

                return {
                    "email": account.get("email"),
                    "name": account.get("name") or profile.get("nickname", ""),
                    "nickname": profile.get("nickname", ""),
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
                    "nickname": naver_data.get("nickname"),
                    "provider": "naver",
                    "provider_id": naver_data.get("id"),
                }

            else:
                raise ValidationError("지원하지 않는 provider입니다.")

        except RequestException as e:
            raise ValidationError(f"{provider} 사용자 정보 요청 중 오류: {e}")
        except KeyError:
            raise ValidationError(f"{provider} 사용자 정보 파싱 실패")

    # 메인 로직
    @staticmethod
    def social_login(provider: str, data: dict[str, Any]) -> dict[str, Any]:

        # 사용자 정보 조회
        user_info = SocialAuthService.get_user_info(provider, data)
        email = user_info.get("email")
        if not email:
            raise ValidationError("소셜 계정에서 이메일을 가져올 수 없습니다.")

        #유저 생성/정보 조회
        user, _ = User.objects.get_or_create(
            email=email,
            defaults={
                "name": user_info.get("name", ""),
                "nickname": user_info.get("nickname", ""),  # 닉네임 저장
                "is_active": True,
            },
        )

        # 소셜 계정 연결
        SocialUser.objects.update_or_create(
            user=user,
            provider=provider,
            defaults={"provider_id": user_info["provider_id"]},
        )

        #JWT 토큰 발급 (공통 util)
        tokens = _issue_tokens(user)
        access_expire_seconds = int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds())  # type: ignore

        #응답 데이터
        return {
            "detail": f"{provider.capitalize()} 로그인에 성공했습니다.",
            "result": {
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "name": user.name,
                    "nickname": getattr(user, "nickname", None),
                    "provider": provider,
                },
                "access_token": tokens["access"],
                "refresh_token": tokens["refresh"],
                "token_type": "Bearer",
                "access_token_expires_in": access_expire_seconds,
            },
        }
