from __future__ import annotations

from typing import Any, Dict, Optional, cast

import requests
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.users.enums import Gender, Provider
from apps.users.models import SocialUser, User
from apps.users.services.auth_services import _issue_tokens


class SocialAuthService:

    # 인가 코드 → access_token 교환
    @staticmethod
    def exchange_code_for_token(provider: str, code: str, state: Optional[str] = None) -> str:
        try:
            token_url: str
            payload: Dict[str, str]

            if provider == Provider.KAKAO.value:
                token_url = "https://kauth.kakao.com/oauth/token"
                payload = {
                    "grant_type": "authorization_code",
                    "client_id": cast(str, settings.KAKAO_CLIENT_ID),
                    "redirect_uri": cast(str, settings.KAKAO_REDIRECT_URI),
                    "code": code,
                }

            elif provider == Provider.NAVER.value:
                token_url = "https://nid.naver.com/oauth2.0/token"
                payload = {
                    "grant_type": "authorization_code",
                    "client_id": cast(str, settings.NAVER_CLIENT_ID),
                    "client_secret": cast(str, settings.NAVER_CLIENT_SECRET),
                    "code": code,
                    "state": state or "RANDOM_STATE_STRING",
                }

            else:
                raise ValidationError({"error": f"지원하지 않는 provider입니다: {provider}"})

            response = requests.post(token_url, data=payload, timeout=5)
            response.raise_for_status()
            token_data: Dict[str, Any] = response.json()
            access_token = token_data.get("access_token")

            if not access_token:
                raise ValidationError({"error": f"{provider} access_token 발급 실패"})

            return cast(str, access_token)

        except requests.RequestException as e:
            raise ValidationError({"error": f"{provider.capitalize()} 토큰 요청 실패: {e}"})

    # access_token으로 사용자 정보 요청
    @staticmethod
    def get_user_info(provider: str, access_token: str) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            if provider == Provider.KAKAO.value:
                resp = requests.get("https://kapi.kakao.com/v2/user/me", headers=headers, timeout=5)
                resp.raise_for_status()
                data = resp.json()
                kakao = data.get("kakao_account", {})
                profile = kakao.get("profile", {})
                return {
                    "email": kakao.get("email", ""),
                    "name": kakao.get("name") or profile.get("nickname", ""),
                    "nickname": profile.get("nickname", ""),
                    "phone_number": kakao.get("phone_number", ""),
                    "birthday": kakao.get("birthday", ""),
                    "gender": kakao.get("gender", ""),
                    "profile_img_url": profile.get("profile_image_url", ""),
                    "provider_id": data.get("id"),
                }

            elif provider == Provider.NAVER.value:
                resp = requests.get("https://openapi.naver.com/v1/nid/me", headers=headers, timeout=5)
                resp.raise_for_status()
                naver = resp.json().get("response", {})
                return {
                    "email": naver.get("email", ""),
                    "name": naver.get("name", ""),
                    "nickname": naver.get("nickname", ""),
                    "phone_number": naver.get("mobile", ""),
                    "birthday": naver.get("birthday", ""),
                    "gender": naver.get("gender", ""),
                    "profile_img_url": naver.get("profile_image", ""),
                    "provider_id": naver.get("id"),
                }

            raise ValidationError({"error": f"지원하지 않는 provider입니다: {provider}"})
        except requests.RequestException as e:
            raise ValidationError({"error": f"{provider.capitalize()} 사용자 정보 요청 실패: {e}"})

    # 로그인/회원가입 처리
    @staticmethod
    def handle_social_login(provider: str, code: str, state: Optional[str] = None) -> Dict[str, Any]:
        """소셜 로그인 메인 처리 (JWT access만 반환)"""
        access_token = SocialAuthService.exchange_code_for_token(provider, code, state=state)
        user_info = SocialAuthService.get_user_info(provider, access_token)
        email = user_info.get("email", "").strip()

        if not email:
            raise ValidationError({"error": "이메일 정보를 가져올 수 없습니다."})

        existing_user: Optional[User] = User.objects.filter(email=email).first()

        if existing_user:
            SocialUser.objects.update_or_create(
                user=existing_user,
                provider=provider,
                defaults={
                    "provider_id": str(user_info.get("provider_id", "")),
                    "updated_at": timezone.now(),
                },
            )
            user = existing_user
        else:
            gender_str = str(user_info.get("gender", "")).lower()
            gender_value = Gender.MALE.value if gender_str in ("male", "m", "남성") else Gender.FEMALE.value

            user = User.objects.create(
                email=email,
                name=user_info.get("name", ""),
                nickname=user_info.get("nickname", ""),
                phone_number=user_info.get("phone_number", "01000000000"),
                birthday=user_info.get("birthday", "2000-01-01"),
                gender=gender_value,
                profile_img_url=user_info.get("profile_img_url", ""),
                is_active=True,
            )

            SocialUser.objects.create(
                user=user,
                provider=provider,
                provider_id=str(user_info.get("provider_id", "")),
            )

        # JWT 발급 (access만 반환)
        tokens = _issue_tokens(user)

        return {
            "detail": f"{provider.capitalize()} 로그인에 성공했습니다.",
            "data": {"access": tokens["access"]},
        }
