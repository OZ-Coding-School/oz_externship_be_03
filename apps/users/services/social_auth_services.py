from __future__ import annotations

from typing import Any, Dict, Optional, cast

import requests
from django.conf import settings
from django.core.exceptions import ValidationError

from apps.users.enums import Gender, Provider
from apps.users.models import SocialUser, User
from apps.users.services.auth_services import _issue_tokens


# 디버깅 관련 코드
def _debug_log_response(prefix: str, response: requests.Response) -> None:
    if settings.DEBUG:
        print(f"\n[{prefix}] 상태 코드: {response.status_code}")
        try:
            print(f"[{prefix}] 응답 본문:", response.json())
        except Exception:
            print(f"[{prefix}] 원본 응답:", response.text)


# 테스트 환경일 때는 무조건 mock
def _is_mock_mode() -> bool:
    from django.conf import settings

    if getattr(settings, "TEST", False):
        return True
    if settings.DEBUG and not getattr(settings, "SOCIAL_AUTH_FORCE_REAL_REQUEST", False):
        return True
    return False


# 카카오
class KakaoAuthService:

    @staticmethod
    def exchange_code_for_token(code: str) -> str:
        if _is_mock_mode() and code.startswith("FAKE_"):
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
            _debug_log_response("KAKAO TOKEN", response)
            if response.status_code != 200:
                raise ValidationError(f"[KakaoTokenError] {response.status_code}: {response.text}")
            token_data: Dict[str, Any] = response.json()
            access_token = token_data.get("access_token")
            if not isinstance(access_token, str):
                raise ValidationError(f"[KakaoTokenError] 액세스 토큰 누락: {token_data}")
            return access_token

        except requests.RequestException as e:
            print(f"[KakaoTokenRequestException] {e}")
            raise ValidationError(f"[KakaoTokenRequestException] 인가 코드 교환 실패: {str(e)}")

    @staticmethod
    def get_user_info(access_token: str) -> Dict[str, Any]:
        if _is_mock_mode() and access_token.startswith("mock_access_token_for_"):
            print("[MOCK] 카카오 사용자 정보 반환")
            return {
                "email": "kakao_test@example.com",
                "name": "테스트유저_카카오",
                "nickname": "kakao_mock",
                "gender": "male",
                "birthday": "1998-10-01",
                "phone_number": "+82 10-1234-5678",
                "profile_img_url": "https://mock.image/kakao.png",
                "provider_id": "1234567890",
            }

        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            resp = requests.get("https://kapi.kakao.com/v2/user/me", headers=headers, timeout=5)
            _debug_log_response("KAKAO USERINFO", resp)
            if resp.status_code != 200:
                raise ValidationError(f"[KakaoUserInfoError] {resp.status_code}: {resp.text}")

            data: Dict[str, Any] = resp.json()
            kakao_account = data.get("kakao_account", {})
            profile = kakao_account.get("profile", {})
            birthdate = kakao_account.get("birthdate") or "1900-01-01"

            return {
                "email": kakao_account.get("email", "") or f"no_email_{data.get('id')}@kakao.local",
                "name": kakao_account.get("name", profile.get("nickname", "")),
                "nickname": profile.get("nickname", ""),
                "gender": kakao_account.get("gender", ""),
                "birthday": birthdate,
                "phone_number": kakao_account.get("phone_number", ""),
                "profile_img_url": profile.get("profile_image_url", ""),
                "provider_id": str(data.get("id", "")),
            }

        except requests.RequestException as e:
            print(f"[KakaoUserInfoException] {e}")
            raise ValidationError(f"[KakaoUserInfoException] 유저 정보를 가져올 수 없습니다: {str(e)}")

    @staticmethod
    def handle_login(code: str) -> Dict[str, Any]:
        access_token = KakaoAuthService.exchange_code_for_token(code)
        user_info = KakaoAuthService.get_user_info(access_token)

        email = user_info.get("email", "").strip() or f"no_email_{user_info.get('provider_id')}@kakao.local"
        birthday = user_info.get("birthday", "1900-01-01")

        user, _ = User.objects.get_or_create(
            email=email,
            defaults={
                "name": user_info.get("name", ""),
                "nickname": user_info.get("nickname", ""),
                "gender": Gender.MALE.value if user_info.get("gender") in ["male", "M"] else Gender.FEMALE.value,
                "birthday": birthday,
                "phone_number": user_info.get("phone_number", ""),
                "profile_img_url": user_info.get("profile_img_url", ""),
                "is_active": True,
            },
        )
        SocialUser.objects.update_or_create(user=user, provider=Provider.KAKAO.value)
        tokens = _issue_tokens(user)
        return {"detail": "카카오 로그인에 성공했습니다.", "data": tokens}


# 네이버
class NaverAuthService:

    @staticmethod
    def exchange_code_for_token(code: str, state: Optional[str]) -> str:
        if _is_mock_mode() and code.startswith("FAKE_"):
            print(f"[MOCK] 네이버 인가 코드 테스트: {code}")
            return "mock_access_token_for_naver"

        if not state:
            raise ValidationError("[NaverStateError] state 값이 누락되었습니다. 요청이 위조되었을 수 있습니다.")

        token_url = "https://nid.naver.com/oauth2.0/token"
        payload = {
            "grant_type": "authorization_code",
            "client_id": cast(str, settings.NAVER_CLIENT_ID),
            "client_secret": cast(str, settings.NAVER_CLIENT_SECRET),
            "code": code,
            "state": state,
        }

        try:
            response = requests.post(token_url, data=payload, timeout=5)
            _debug_log_response("NAVER TOKEN", response)

            if response.status_code != 200:
                raise ValidationError(f"[NaverTokenError] {response.status_code}: {response.text}")

            token_data: Dict[str, Any] = response.json()
            access_token = token_data.get("access_token")
            if not isinstance(access_token, str):
                raise ValidationError(f"[NaverTokenError] 액세스 토큰 누락: {token_data}")

            return access_token

        except requests.RequestException as e:
            print(f"[NaverTokenRequestException] {e}")
            raise ValidationError(f"[NaverTokenRequestException] 인가 코드 교환 실패: {str(e)}")

    @staticmethod
    def get_user_info(access_token: str) -> Dict[str, Any]:
        if _is_mock_mode() and access_token.startswith("mock_access_token_for_"):
            print("[MOCK] 네이버 사용자 정보 반환")
            return {
                "email": "naver_test@example.com",
                "name": "테스트유저_네이버",
                "nickname": "naver_mock",
                "gender": "female",
                "birthday": "1995-08-15",
                "phone_number": "+82 10-9876-5432",
                "profile_img_url": "https://mock.image/naver.png",
                "provider_id": "9876543210",
            }

        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            resp = requests.get("https://openapi.naver.com/v1/nid/me", headers=headers, timeout=5)
            _debug_log_response("NAVER USERINFO", resp)
            if resp.status_code != 200:
                raise ValidationError(f"[NaverUserInfoError] {resp.status_code}: {resp.text}")

            naver_account = resp.json().get("response", {})
            birthyear = naver_account.get("birthyear", "")
            birthday_fragment = naver_account.get("birthday", "")
            birthday = f"{birthyear}-{birthday_fragment}" if birthyear and birthday_fragment else "1900-01-01"

            return {
                "email": naver_account.get("email", "") or f"no_email_{naver_account.get('id')}@naver.local",
                "name": naver_account.get("name", ""),
                "nickname": naver_account.get("nickname", ""),
                "gender": naver_account.get("gender", ""),
                "birthday": birthday,
                "phone_number": naver_account.get("mobile", ""),
                "profile_img_url": naver_account.get("profile_image", ""),
                "provider_id": str(naver_account.get("id", "")),
            }

        except requests.RequestException as e:
            print(f"[NaverUserInfoException] {e}")
            raise ValidationError(f"[NaverUserInfoException] 유저 정보를 가져올 수 없습니다: {str(e)}")

    @staticmethod
    def handle_login(code: str, state: Optional[str]) -> Dict[str, Any]:
        access_token = NaverAuthService.exchange_code_for_token(code, state)
        user_info = NaverAuthService.get_user_info(access_token)

        email = user_info.get("email", "").strip() or f"no_email_{user_info.get('provider_id')}@naver.local"
        birthday = user_info.get("birthday", "1900-01-01")

        user, _ = User.objects.get_or_create(
            email=email,
            defaults={
                "name": user_info.get("name", ""),
                "nickname": user_info.get("nickname", ""),
                "gender": Gender.MALE.value if user_info.get("gender") in ["male", "M"] else Gender.FEMALE.value,
                "birthday": birthday,
                "phone_number": user_info.get("phone_number", ""),
                "profile_img_url": user_info.get("profile_img_url", ""),
                "is_active": True,
            },
        )
        SocialUser.objects.update_or_create(user=user, provider=Provider.NAVER.value)
        tokens = _issue_tokens(user)
        return {"detail": "네이버 로그인에 성공했습니다.", "data": tokens}


#진입점
class SocialAuthService:

    @staticmethod
    def handle_social_login(provider: str, code: str, state: Optional[str] = None) -> Dict[str, Any]:
        if provider == Provider.KAKAO.value:
            return KakaoAuthService.handle_login(code)
        if provider == Provider.NAVER.value:
            return NaverAuthService.handle_login(code, state)
        raise ValidationError("지원하지 않는 소셜 로그인 제공자입니다.")
