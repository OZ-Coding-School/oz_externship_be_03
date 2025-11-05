# mypy: ignore-missing-imports
from __future__ import annotations

from typing import Any, Dict, Optional

import requests
from allauth.socialaccount.providers.kakao.views import (
    KakaoOAuth2Adapter,  # type: ignore[import-untyped]
)
from allauth.socialaccount.providers.naver.views import (
    NaverOAuth2Adapter,  # type: ignore[import-untyped]
)
from allauth.socialaccount.providers.oauth2.client import (
    OAuth2Error,  # type: ignore[import-untyped]
)
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from apps.users.enums import Gender, Provider
from apps.users.models import SocialUser, User
from apps.users.services.auth_services import _issue_tokens


class SocialAuthService:
    """소셜 로그인 서비스"""

    # 인가 코드 → access_token 교환
    @staticmethod
    def exchange_code_for_token(provider: str, code: str) -> str:
        """OAuth 인가 코드로 access token 교환"""
        try:
            if provider == Provider.KAKAO.value:
                adapter = KakaoOAuth2Adapter()
            elif provider == Provider.NAVER.value:
                adapter = NaverOAuth2Adapter()
            else:
                raise ValidationError({"error": f"지원하지 않는 provider입니다: {provider}"})

            token = adapter.get_access_token(code)
            return str(token.token)

        except OAuth2Error as e:
            raise ValidationError({"error": f"{provider.capitalize()} 토큰 교환 실패: {e}"})
        except Exception as e:
            raise ValidationError({"error": f"{provider.capitalize()} 토큰 요청 중 예외 발생: {e}"})

    # 사용자 정보 가져오기
    @staticmethod
    def get_user_info(provider: str, access_token: str) -> Dict[str, Any]:
        """access_token으로 사용자 정보 조회"""
        try:
            headers: Dict[str, str] = {"Authorization": f"Bearer {access_token}"}

            if provider == Provider.KAKAO.value:
                resp = requests.get("https://kapi.kakao.com/v2/user/me", headers=headers, timeout=5)
                resp.raise_for_status()
                kakao_data: Dict[str, Any] = resp.json()
                account: Dict[str, Any] = kakao_data.get("kakao_account", {})
                profile: Dict[str, Any] = account.get("profile", {})

                return {
                    "email": account.get("email", ""),
                    "name": account.get("name") or profile.get("nickname", ""),
                    "nickname": profile.get("nickname", ""),
                    "phone_number": account.get("phone_number", ""),
                    "birthday": account.get("birthday", ""),
                    "gender": account.get("gender", ""),
                    "profile_img_url": profile.get("profile_image_url", ""),
                    "provider_id": kakao_data.get("id"),
                }

            elif provider == Provider.NAVER.value:
                resp = requests.get("https://openapi.naver.com/v1/nid/me", headers=headers, timeout=5)
                resp.raise_for_status()
                raw_data: Dict[str, Any] = resp.json()
                naver_data: Dict[str, Any] = raw_data.get("response", {})

                return {
                    "email": naver_data.get("email", ""),
                    "name": naver_data.get("name", ""),
                    "nickname": naver_data.get("nickname", ""),
                    "phone_number": naver_data.get("mobile", ""),
                    "birthday": naver_data.get("birthday", ""),
                    "gender": naver_data.get("gender", ""),
                    "profile_img_url": naver_data.get("profile_image", ""),
                    "provider_id": naver_data.get("id"),
                }

            else:
                raise ValidationError({"error": f"지원하지 않는 provider입니다: {provider}"})

        except requests.RequestException as e:
            raise ValidationError({"error": f"{provider.capitalize()} 사용자 정보 요청 실패: {e}"})

    # 로그인 / 회원가입 처리
    @staticmethod
    def handle_social_login(provider: str, code: str) -> Dict[str, str]:
        """소셜 로그인 메인 처리 함수"""

        access_token: str = SocialAuthService.exchange_code_for_token(provider, code)
        user_info: Dict[str, Any] = SocialAuthService.get_user_info(provider, access_token)
        email: str = str(user_info.get("email", "")).strip()

        if not email:
            raise ValidationError({"error": "이메일 정보를 가져올 수 없습니다."})

        # 기존 유저 → 로그인
        existing_user: Optional[User] = User.objects.filter(email=email).first()
        if existing_user is not None:
            SocialUser.objects.update_or_create(
                user=existing_user,
                provider=provider,
                defaults={
                    "provider_id": str(user_info.get("provider_id", "")),
                    "updated_at": timezone.now(),
                },
            )

            issued_tokens: Dict[str, str] = _issue_tokens(existing_user)
            return {
                "detail": f"{provider.capitalize()} 로그인에 성공했습니다.",
                "access": issued_tokens.get("access", ""),
                "refresh": issued_tokens.get("refresh", ""),
            }

        # 신규 유저 생성
        gender_str = str(user_info.get("gender", "")).lower()
        # ✅ Gender Enum은 M/F만 있음 → 기본값 F로 지정
        gender_value: str = Gender.MALE.value if gender_str in ("male", "m", "남성", "m") else Gender.FEMALE.value

        try:
            user: User = User.objects.create(
                email=email,
                name=user_info.get("name", ""),
                nickname=user_info.get("nickname", ""),
                phone_number=user_info.get("phone_number", "01000000000"),
                birthday=user_info.get("birthday", "2000-01-01"),
                gender=gender_value,
                profile_img_url=user_info.get("profile_img_url", ""),
                is_active=True,
            )
        except IntegrityError:
            raise ValidationError({"error": "회원 생성 중 중복된 정보가 있습니다."})

        # 소셜 유저 연동
        SocialUser.objects.create(
            user=user,
            provider=provider,
            provider_id=str(user_info.get("provider_id", "")),
        )

        new_tokens: Dict[str, str] = _issue_tokens(user)
        return {
            "detail": f"{provider.capitalize()} 로그인에 성공했습니다.",
            "access": new_tokens.get("access", ""),
            "refresh": new_tokens.get("refresh", ""),
        }
