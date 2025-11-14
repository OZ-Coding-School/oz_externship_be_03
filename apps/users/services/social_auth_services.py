from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, cast

import requests
from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError

from apps.users.enums import Gender, Provider
from apps.users.models import SocialUser, User
from apps.users.services.auth_services import _issue_tokens
from apps.users.validators import normalize_phone, validate_korean_phone

logger = logging.getLogger(__name__)
DEFAULT_PROFILE_IMAGE_URL = "https://oz-externship.s3.ap-northeast-2.amazonaws.com/default_user_icon.png"


# 공통
def _debug_log_response(prefix: str, response: requests.Response) -> None:
    if settings.DEBUG:
        logger.info(f"\n[{prefix}] 상태 코드: {response.status_code}")
        try:
            logger.info(f"[{prefix}] 응답 본문:", response.json())
        except Exception:
            logger.info(f"[{prefix}] 원본 응답:", response.text)


def _convert_gender(value: Optional[str]) -> str:
    if not value:
        return Gender.MALE.value
    v = value.lower()
    if v.startswith("m"):
        return Gender.MALE.value
    if v.startswith("f"):
        return Gender.FEMALE.value
    return Gender.MALE.value


# 카카오
class KakaoAuthService:
    @staticmethod
    def exchange_code_for_token(code: str) -> str:
        token_url = "https://kauth.kakao.com/oauth/token"
        payload: Dict[str, str] = {
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

            token_data = response.json()
            access_token = token_data.get("access_token")
            if not isinstance(access_token, str):
                raise ValidationError(f"[KakaoTokenError] 액세스 토큰 누락: {token_data}")
            return access_token

        except requests.RequestException as e:
            raise ValidationError(f"[KakaoTokenRequestException] 인가 코드 교환 실패: {str(e)}")

    def _get_birthday(self, kakao_account: dict[str, Any]) -> str:
        birthyear = kakao_account.get("birthyear")
        birthday = kakao_account.get("birthdate")

        if not birthyear or not birthday:
            return timezone.now().strftime("%Y-%m-%d")

        return f"{birthyear}-{birthday[:2]}-{birthday[2:]}"

    def _get_phone_number(self, kakao_account: dict[str, Any]) -> str:
        phone_number = kakao_account.get("phone_number")
        if not phone_number:
            return ""
        return normalize_phone(phone_number)

    def _get_provider_id(self, response_data: dict[str, Any]) -> str:
        provider_id: str = response_data.get("id", "")
        if not provider_id:
            logger.error("[ERROR] 카카오 사용자 정보 조회 응답으로부터 provider_id 가 누락되었습니다.")
            raise APIException("카카오 인증서버 응답에서 필수 데이터가 누락되었습니다.")
        return provider_id

    def _get_gender(self, kakao_account: dict[str, Any]) -> str:
        gender = kakao_account.get("gender", "")
        if not gender:
            return Gender.MALE

        return _convert_gender(gender)

    def _get_nickname(self, profile_data: dict[str, Any]) -> str:
        nickname: str = profile_data.get("nickname", "")
        if not nickname:
            return "kakao_user" + uuid.uuid4().hex[:8]
        return nickname

    def _get_name(self, kakao_account: dict[str, Any]) -> str:
        name: str = kakao_account.get("name", "")
        if not name:
            return self._get_nickname(kakao_account)
        return name

    def _get_email(self, kakao_account: dict[str, Any]) -> str:
        email: str = kakao_account.get("email", "")
        if not email:
            logger.error("[ERROR] 카카오 사용자 정보 조회 응답으로부터 email 이 누락되었습니다.")
            raise APIException("카카오 인증서버 응답에서 필수 데이터가 누락되었습니다.")
        return email

    def _get_profile_img_url(self, profile_data: dict[str, Any]) -> str:
        profile_img_url: str = profile_data.get("profile_image_url", "")
        if not profile_img_url:
            return DEFAULT_PROFILE_IMAGE_URL
        return profile_img_url

    def get_user_info(self, access_token: str) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            resp = requests.get("https://kapi.kakao.com/v2/user/me", headers=headers, timeout=5)
            _debug_log_response("KAKAO USERINFO", resp)
            if resp.status_code != 200:
                raise ValidationError(f"[KakaoUserInfoError] {resp.status_code}: {resp.text}")

            data = resp.json()
            kakao_account: Dict[str, Any] = data.get("kakao_account", {})
            profile: Dict[str, Any] = kakao_account.get("profile", {})

            return {
                "email": self._get_email(kakao_account),
                "name": self._get_name(kakao_account),
                "nickname": self._get_nickname(profile),
                "gender": self._get_gender(kakao_account),
                "birthday": self._get_birthday(kakao_account),
                "phone_number": self._get_phone_number(kakao_account),
                "profile_img_url": self._get_profile_img_url(profile),
                "provider_id": self._get_provider_id(data),
            }

        except requests.RequestException as e:
            raise ValidationError(f"[KakaoUserInfoException] 유저 정보를 가져올 수 없습니다: {str(e)}")

    def handle_login(self, code: str) -> Dict[str, Any]:
        access_token = KakaoAuthService.exchange_code_for_token(code)
        user_info = KakaoAuthService.get_user_info(self, access_token)
        provider_id = user_info.pop("provider_id")

        created = False

        try:
            existing_user = User.objects.get(email=user_info["email"])
            linked_social_exists = SocialUser.objects.filter(user=existing_user, provider=Provider.KAKAO.value).exists()
            if linked_social_exists:
                tokens = _issue_tokens(existing_user)
            else:
                # 일반 회원 → 소셜 테이블 생성 + 로그인 처리
                SocialUser.objects.create(
                    user=existing_user,
                    provider=Provider.KAKAO.value,
                    provider_id=provider_id,
                )
                tokens = _issue_tokens(existing_user)
                created = True

        except User.DoesNotExist:
            user = User.objects.create(is_active=True, **user_info)
            SocialUser.objects.create(
                user=user,
                provider=Provider.KAKAO.value,
                provider_id=provider_id,
            )
            tokens = _issue_tokens(user)
            created = True

        return {"detail": "카카오 로그인에 성공했습니다.", "data": tokens, "created": created}


# 네이버
class NaverAuthService:
    @staticmethod
    def exchange_code_for_token(code: str, state: Optional[str]) -> str:
        token_url = "https://nid.naver.com/oauth2.0/token"
        payload: Dict[str, str] = {
            "grant_type": "authorization_code",
            "client_id": cast(str, settings.NAVER_CLIENT_ID),
            "client_secret": cast(str, settings.NAVER_CLIENT_SECRET),
            "code": code,
            "state": state or "",
        }

        try:
            response = requests.post(token_url, data=payload, timeout=5)
            _debug_log_response("NAVER TOKEN", response)
            if response.status_code != 200:
                raise ValidationError(f"[NaverTokenError] {response.status_code}: {response.text}")

            token_data = response.json()
            access_token = token_data.get("access_token")
            if not isinstance(access_token, str):
                raise ValidationError(f"[NaverTokenError] 액세스 토큰 누락: {token_data}")
            return access_token

        except requests.RequestException as e:
            raise ValidationError(f"[NaverTokenRequestException] 인가 코드 교환 실패: {str(e)}")

    @staticmethod
    def get_user_info(access_token: str) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            resp = requests.get("https://openapi.naver.com/v1/nid/me", headers=headers, timeout=5)
            _debug_log_response("NAVER USERINFO", resp)
            if resp.status_code != 200:
                raise ValidationError(f"[NaverUserInfoError] {resp.status_code}: {resp.text}")

            naver_account: Dict[str, Any] = resp.json().get("response", {})
            birthyear = naver_account.get("birthyear")
            birthday_fragment = naver_account.get("birthday")

            birthday: Optional[str] = None
            if isinstance(birthyear, str) and isinstance(birthday_fragment, str):
                try:
                    full_date = f"{birthyear}-{birthday_fragment}"
                    datetime.strptime(full_date, "%Y-%m-%d")
                    birthday = full_date
                except ValueError:
                    birthday = None

            phone_number = normalize_phone(naver_account.get("mobile") or "")

            return {
                "email": cast(str, naver_account.get("email") or f"no_email_{naver_account.get('id')}@naver.local"),
                "name": cast(str, naver_account.get("name") or ""),
                "nickname": cast(str, naver_account.get("nickname") or "네이버사용자"),
                "gender": cast(str, naver_account.get("gender") or ""),
                "birthday": birthday,
                "phone_number": phone_number,
                "profile_img_url": cast(str, naver_account.get("profile_image") or ""),
                "provider_id": cast(str, naver_account.get("id") or ""),
            }

        except requests.RequestException as e:
            raise ValidationError(f"[NaverUserInfoException] 유저 정보를 가져올 수 없습니다: {str(e)}")

    @staticmethod
    def handle_login(code: str, state: str) -> Dict[str, Any]:
        access_token = NaverAuthService.exchange_code_for_token(code, state)
        user_info = NaverAuthService.get_user_info(access_token)

        email = cast(str, user_info.get("email") or "")
        provider_id = cast(str, user_info.get("provider_id") or "")
        phone_number = normalize_phone(user_info.get("phone_number") or "")

        created = False
        try:
            existing_user = User.objects.get(email=email)
            linked_social_exists = SocialUser.objects.filter(user=existing_user, provider=Provider.NAVER.value).exists()
            if linked_social_exists:
                # 동일 소셜 → 로그인 처리
                tokens = _issue_tokens(existing_user)
            else:
                # 일반 회원 → 소셜 테이블 새로 생성 + 로그인 처리
                SocialUser.objects.create(
                    user=existing_user,
                    provider=Provider.NAVER.value,
                    provider_id=provider_id,
                )
                tokens = _issue_tokens(existing_user)
                created = True
        except User.DoesNotExist:
            # 신규 가입 처리
            nickname = cast(str, user_info.get("nickname") or "")
            if User.objects.filter(nickname=nickname).exists():
                nickname = f"{nickname}_{User.objects.count() + 1}"

            user = User.objects.create(
                email=email,
                name=cast(str, user_info.get("name") or ""),
                nickname=nickname,
                gender=_convert_gender(user_info.get("gender")),
                birthday=cast(str, user_info.get("birthday") or ""),
                phone_number=phone_number,
                profile_img_url=cast(str, user_info.get("profile_img_url") or ""),
                is_active=True,
            )

            SocialUser.objects.create(
                user=user,
                provider=Provider.NAVER.value,
                provider_id=provider_id,
            )

            tokens = _issue_tokens(user)
            created = True

        return {"detail": "네이버 로그인에 성공했습니다.", "data": tokens, "created": created}
