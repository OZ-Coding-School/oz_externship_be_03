from __future__ import annotations

from typing import Any, Dict

import requests
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from requests.exceptions import RequestException

from apps.users.enums import Gender, Provider
from apps.users.models import SocialUser, User
from apps.users.services.auth_services import _issue_tokens


class SocialAuthService:
    """소셜 로그인 서비스"""

    # 사용자 정보 조회
    @staticmethod
    def get_user_info(provider: str, access_token: str) -> Dict[str, str]:
        if not access_token:
            raise ValidationError(f"{provider.capitalize()} access_token이 필요합니다.")

        try:
            if provider == Provider.KAKAO:
                headers = {"Authorization": f"Bearer {access_token}"}
                response = requests.get("https://kapi.kakao.com/v2/user/me", headers=headers)
                response.raise_for_status()
                kakao_data: dict[str, Any] = response.json()
                account: dict[str, Any] = kakao_data.get("kakao_account", {})
                profile: dict[str, Any] = account.get("profile", {})

                return {
                    "email": str(account.get("email") or ""),
                    "name": str(account.get("name") or profile.get("nickname") or ""),
                    "nickname": str(profile.get("nickname") or ""),
                    "phone_number": str(account.get("phone_number") or ""),
                    "birthday": str(account.get("birthday") or ""),
                    "gender": str(account.get("gender") or ""),
                    "profile_img_url": str(profile.get("profile_image_url") or ""),
                    "provider": Provider.KAKAO,
                    "provider_id": str(kakao_data.get("id") or ""),
                }

            elif provider == Provider.NAVER:
                headers = {"Authorization": f"Bearer {access_token}"}
                response = requests.get("https://openapi.naver.com/v1/nid/me", headers=headers)
                response.raise_for_status()
                naver_data: dict[str, Any] = response.json().get("response", {})

                return {
                    "email": str(naver_data.get("email") or ""),
                    "name": str(naver_data.get("name") or ""),
                    "nickname": str(naver_data.get("nickname") or ""),
                    "phone_number": str(naver_data.get("mobile") or ""),
                    "birthday": str(naver_data.get("birthday") or ""),
                    "gender": str(naver_data.get("gender") or ""),
                    "profile_img_url": str(naver_data.get("profile_image") or ""),
                    "provider": Provider.NAVER,
                    "provider_id": str(naver_data.get("id") or ""),
                }

            else:
                raise ValidationError(f"지원하지 않는 provider입니다: {provider}")

        except RequestException as e:
            raise ValidationError(f"{provider.capitalize()} 사용자 정보 요청 중 오류: {e}")

    # 회원가입 / 로그인
    @staticmethod
    def social_login(provider: str, code: str) -> Dict[str, str]:
        """인가코드 → access_token 교환 → 사용자 정보 저장 (응답은 detail 메시지만 반환)"""

        token_url = (
            "https://kauth.kakao.com/oauth/token"
            if provider == Provider.KAKAO
            else "https://nid.naver.com/oauth2.0/token"
        )
        payload: Dict[str, str] = {"grant_type": "authorization_code", "code": code}

        if provider == Provider.KAKAO:
            payload.update(
                {
                    "client_id": str(settings.KAKAO_CLIENT_ID or ""),
                    "redirect_uri": str(settings.KAKAO_REDIRECT_URI or ""),
                }
            )
        else:
            payload.update(
                {
                    "client_id": str(settings.NAVER_CLIENT_ID or ""),
                    "client_secret": str(settings.NAVER_CLIENT_SECRET or ""),
                }
            )

        # access_token 요청
        response = requests.post(token_url, data=payload)
        response.raise_for_status()
        access_token: str = str(response.json().get("access_token") or "")
        if not access_token:
            raise ValidationError(f"{provider.capitalize()} access_token을 가져올 수 없습니다.")

        # 사용자 정보 조회
        user_info = SocialAuthService.get_user_info(provider, access_token)
        email: str = user_info.get("email", "")
        if not email:
            raise ValidationError(f"{provider.capitalize()} 계정에서 이메일을 가져올 수 없습니다.")

        # 기존 유저 존재 → 로그인
        existing_user = User.objects.filter(email=email).first()
        if existing_user:
            _issue_tokens(existing_user)
            return {"detail": f"{provider.capitalize()} 로그인에 성공했습니다."}

        # 신규 회원 생성
        gender_value = user_info.get("gender", "").lower()
        if gender_value in ("male", "m"):
            gender = Gender.MALE.value
        elif gender_value in ("female", "f"):
            gender = Gender.FEMALE.value
        else:
            raise ValidationError(f"{provider.capitalize()} 계정에서 유효하지 않은 성별 형식입니다.")

        try:
            user = User.objects.create(
                email=email,
                name=user_info.get("name", ""),
                nickname=user_info.get("nickname", ""),
                phone_number=user_info.get("phone_number", "01000000000"),
                birthday=user_info.get("birthday", "2000-01-01"),
                gender=gender,
                profile_img_url=user_info.get("profile_img_url", ""),
                is_active=True,
            )
        except IntegrityError as e:
            raise ValidationError(f"{provider.capitalize()} 회원 생성 중 중복된 정보가 있습니다: {e}")

        # 소셜 계정 연결
        try:
            SocialUser.objects.create(
                user=user,
                provider=provider,
                provider_id=user_info.get("provider_id", ""),
            )
        except IntegrityError:
            return {"detail": f"{provider.capitalize()} 로그인에 성공했습니다."}

        # 토큰 발급
        _issue_tokens(user)

        return {"detail": f"{provider.capitalize()} 로그인에 성공했습니다."}
