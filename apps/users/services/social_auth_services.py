from __future__ import annotations

from typing import Any, Dict, Optional, cast

import requests
from django.conf import settings
from django.core.exceptions import ValidationError

from apps.users.enums import Gender, Provider
from apps.users.models import SocialUser, User
from apps.users.services.auth_services import _issue_tokens


# =====================================================
# ✅ 카카오 로그인 서비스
# =====================================================
class KakaoAuthService:


    @staticmethod
    def exchange_code_for_token(code: str) -> str:

        # ✅ 테스트 환경 목 처리
        if settings.DEBUG and code.startswith("FAKE_"):
            print(f"[MOCK] 카카오 인가 코드 테스트: {code}")
            return "mock_access_token_for_kakao"

        token_url = "https://kauth.kakao.com/oauth/token"
        payload = {
            "grant_type": "authorization_code",
            "client_id": cast(str, settings.KAKAO_CLIENT_ID),
            "redirect_uri": cast(str, settings.KAKAO_REDIRECT_URI),
            "code": code,
        }

        try:
            response = requests.post(token_url, data=payload, timeout=5)
            if response.status_code == 400:
                raise ValidationError("인가 코드 형식이 올바르지 않습니다.")
            response.raise_for_status()

            token_data: Dict[str, Any] = response.json()
            access_token = token_data.get("access_token")

            if not isinstance(access_token, str):
                raise ValidationError("액세스 토큰이 발급되지 않았습니다.")
            return access_token

        except requests.RequestException:
            raise ValidationError("인가 코드 형식이 올바르지 않습니다.")

    @staticmethod
    def get_user_info(access_token: str) -> Dict[str, Any]:

        if settings.DEBUG and access_token.startswith("mock_access_token_for_"):
            print("[MOCK] 카카오 사용자 정보 반환")
            return {
                "email": "kakao_test@example.com",
                "name": "테스트유저_카카오",
                "nickname": "kakao_mock",
                "gender": "male",
                "birthday": "1001",
                "birthyear": "1998",
                "phone_number": "+82 10-1234-5678",
                "profile_img_url": "https://mock.image/kakao.png",
                "provider_id": "1234567890",
            }

        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            resp = requests.get("https://kapi.kakao.com/v2/user/me", headers=headers, timeout=5)
            resp.raise_for_status()
            data: Dict[str, Any] = resp.json()
            kakao_account = data.get("kakao_account", {})
            profile = kakao_account.get("profile", {})

            return {
                "email": kakao_account.get("email", ""),
                "name": kakao_account.get("name", profile.get("nickname", "")),
                "nickname": profile.get("nickname", ""),
                "gender": kakao_account.get("gender", ""),
                "birthday": kakao_account.get("birthday", ""),
                "birthyear": kakao_account.get("birthyear", ""),
                "phone_number": kakao_account.get("phone_number", ""),
                "profile_img_url": profile.get("profile_image_url", ""),
                "provider_id": str(data.get("id", "")),
            }

        except requests.RequestException:
            raise ValidationError("유저 정보를 가져올 수 없습니다.")

    @staticmethod
    def handle_login(code: str) -> Dict[str, Any]:

        access_token = KakaoAuthService.exchange_code_for_token(code)
        user_info = KakaoAuthService.get_user_info(access_token)

        email = user_info.get("email", "").strip()
        if not email:
            raise ValidationError("유저 정보를 가져올 수 없습니다.")

        user, _ = User.objects.get_or_create(
            email=email,
            defaults={
                "name": user_info.get("name", ""),
                "nickname": user_info.get("nickname", ""),
                "gender": Gender.MALE.value if user_info.get("gender") in ["male", "M"] else Gender.FEMALE.value,
                "birthday": f"{user_info.get('birthyear', '')}-{user_info.get('birthday', '')[:2]}-{user_info.get('birthday', '')[2:]}",
                "phone_number": user_info.get("phone_number", ""),
                "profile_img_url": user_info.get("profile_img_url", ""),
                "is_active": True,
            },
        )

        SocialUser.objects.update_or_create(user=user, provider=Provider.KAKAO.value)
        tokens = _issue_tokens(user)

        return {
            "detail": "카카오 로그인에 성공했습니다.",
            "data": {"access": tokens["access"], "refresh": tokens["refresh"]},
        }


# =====================================================
# ✅ 네이버 로그인 서비스
# =====================================================
class NaverAuthService:
    """네이버 소셜 로그인 서비스"""

    @staticmethod
    def exchange_code_for_token(code: str, state: Optional[str]) -> str:
        """인가 코드(code) + state → access_token 교환"""
        # ✅ 테스트 환경 목 처리
        if settings.DEBUG and code.startswith("FAKE_"):
            print(f"[MOCK] 네이버 인가 코드 테스트: {code}")
            return "mock_access_token_for_naver"

        token_url = "https://nid.naver.com/oauth2.0/token"
        payload = {
            "grant_type": "authorization_code",
            "client_id": cast(str, settings.NAVER_CLIENT_ID),
            "client_secret": cast(str, settings.NAVER_CLIENT_SECRET),
            "code": code,
            "state": state or "RANDOM_STATE_STRING",
        }

        try:
            response = requests.post(token_url, data=payload, timeout=5)
            if response.status_code == 400:
                raise ValidationError("인가 코드 형식이 올바르지 않습니다.")
            response.raise_for_status()

            token_data: Dict[str, Any] = response.json()
            access_token = token_data.get("access_token")

            if not isinstance(access_token, str):
                raise ValidationError("액세스 토큰이 발급되지 않았습니다.")
            return access_token

        except requests.RequestException:
            raise ValidationError("인가 코드 형식이 올바르지 않습니다.")

    @staticmethod
    def get_user_info(access_token: str) -> Dict[str, Any]:
        """네이버 사용자 정보 조회"""
        # ✅ 테스트 환경 목 처리
        if settings.DEBUG and access_token.startswith("mock_access_token_for_"):
            print("[MOCK] 네이버 사용자 정보 반환")
            return {
                "email": "naver_test@example.com",
                "name": "테스트유저_네이버",
                "nickname": "naver_mock",
                "gender": "female",
                "birthday": "0815",
                "birthyear": "1995",
                "phone_number": "+82 10-9876-5432",
                "profile_img_url": "https://mock.image/naver.png",
                "provider_id": "9876543210",
            }

        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            resp = requests.get("https://openapi.naver.com/v1/nid/me", headers=headers, timeout=5)
            resp.raise_for_status()
            naver_account = resp.json().get("response", {})

            return {
                "email": naver_account.get("email", ""),
                "name": naver_account.get("name", ""),
                "nickname": naver_account.get("nickname", ""),
                "gender": naver_account.get("gender", ""),
                "birthday": naver_account.get("birthday", ""),
                "birthyear": naver_account.get("birthyear", ""),
                "phone_number": naver_account.get("mobile", ""),
                "profile_img_url": naver_account.get("profile_image", ""),
                "provider_id": str(naver_account.get("id", "")),
            }

        except requests.RequestException:
            raise ValidationError("유저 정보를 가져올 수 없습니다.")

    @staticmethod
    def handle_login(code: str, state: Optional[str]) -> Dict[str, Any]:
        """네이버 로그인 메인 처리"""
        access_token = NaverAuthService.exchange_code_for_token(code, state)
        user_info = NaverAuthService.get_user_info(access_token)

        email = user_info.get("email", "").strip()
        if not email:
            raise ValidationError("유저 정보를 가져올 수 없습니다.")

        user, _ = User.objects.get_or_create(
            email=email,
            defaults={
                "name": user_info.get("name", ""),
                "nickname": user_info.get("nickname", ""),
                "gender": Gender.MALE.value if user_info.get("gender") in ["male", "M"] else Gender.FEMALE.value,
                "birthday": f"{user_info.get('birthyear', '')}-{user_info.get('birthday', '')[:2]}-{user_info.get('birthday', '')[2:]}",
                "phone_number": user_info.get("phone_number", ""),
                "profile_img_url": user_info.get("profile_img_url", ""),  # ✅ 통일
                "is_active": True,
            },
        )

        SocialUser.objects.update_or_create(user=user, provider=Provider.NAVER.value)
        tokens = _issue_tokens(user)

        return {
            "detail": "네이버 로그인에 성공했습니다.",
            "data": {"access": tokens["access"], "refresh": tokens["refresh"]},
        }


# =====================================================
# ✅ 통합 진입점
# =====================================================
class SocialAuthService:
    """공통 소셜 로그인 진입점"""

    @staticmethod
    def handle_social_login(provider: str, code: str, state: Optional[str] = None) -> Dict[str, Any]:
        if provider == Provider.KAKAO.value:
            return KakaoAuthService.handle_login(code)
        if provider == Provider.NAVER.value:
            return NaverAuthService.handle_login(code, state)
        raise ValidationError("지원하지 않는 소셜 로그인 제공자입니다.")
