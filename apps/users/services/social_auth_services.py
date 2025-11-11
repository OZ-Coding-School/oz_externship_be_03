from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional, cast

import requests
from django.conf import settings
from rest_framework.exceptions import ValidationError

from apps.users.enums import Gender, Provider
from apps.users.models import SocialUser, User
from apps.users.services.auth_services import _issue_tokens
from apps.users.validators import normalize_phone, validate_korean_phone


# 공통
def _debug_log_response(prefix: str, response: requests.Response) -> None:
    if settings.DEBUG:
        print(f"\n[{prefix}] 상태 코드: {response.status_code}")
        try:
            print(f"[{prefix}] 응답 본문:", response.json())
        except Exception:
            print(f"[{prefix}] 원본 응답:", response.text)


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

    @staticmethod
    def get_user_info(access_token: str) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            resp = requests.get("https://kapi.kakao.com/v2/user/me", headers=headers, timeout=5)
            _debug_log_response("KAKAO USERINFO", resp)
            if resp.status_code != 200:
                raise ValidationError(f"[KakaoUserInfoError] {resp.status_code}: {resp.text}")

            data = resp.json()
            kakao_account: Dict[str, Any] = data.get("kakao_account", {})
            profile: Dict[str, Any] = kakao_account.get("profile", {})

            # 생년월일
            birthday: Optional[str] = None
            birthdate = kakao_account.get("birthdate")
            if isinstance(birthdate, str):
                try:
                    datetime.strptime(birthdate, "%Y-%m-%d")
                    birthday = birthdate
                except ValueError:
                    birthday = None
            else:
                birthyear = kakao_account.get("birthyear")
                birthday_fragment = kakao_account.get("birthday")
                if isinstance(birthyear, str) and isinstance(birthday_fragment, str) and len(birthday_fragment) == 4:
                    formatted = f"{birthyear}-{birthday_fragment[:2]}-{birthday_fragment[2:]}"
                    try:
                        datetime.strptime(formatted, "%Y-%m-%d")
                        birthday = formatted
                    except ValueError:
                        print(f"[WARN] 잘못된 생년월일 조합: {formatted}")

            # 전화번호 정규화
            raw_phone = kakao_account.get("phone_number", "")
            phone_number = normalize_phone(raw_phone)
            if phone_number:
                try:
                    validate_korean_phone(phone_number)
                except ValidationError:
                    print(f"[WARN] 잘못된 전화번호 형식 감지: {raw_phone} → {phone_number}")
                    phone_number = ""

            return {
                "email": cast(str, kakao_account.get("email") or f"no_email_{data.get('id')}@kakao.local"),
                "name": cast(str, kakao_account.get("name") or profile.get("nickname") or ""),
                "nickname": cast(str, profile.get("nickname") or "카카오사용자"),
                "gender": cast(str, kakao_account.get("gender") or ""),
                "birthday": birthday,
                "phone_number": phone_number,
                "profile_img_url": cast(str, profile.get("profile_image_url") or ""),
                "provider_id": cast(str, data.get("id") or ""),
            }

        except requests.RequestException as e:
            raise ValidationError(f"[KakaoUserInfoException] 유저 정보를 가져올 수 없습니다: {str(e)}")

    @staticmethod
    def handle_login(code: str) -> Dict[str, Any]:
        access_token = KakaoAuthService.exchange_code_for_token(code)
        user_info = KakaoAuthService.get_user_info(access_token)

        email = cast(str, user_info.get("email") or "")
        provider_id = cast(str, user_info.get("provider_id") or "")
        phone_number = normalize_phone(user_info.get("phone_number") or "")

        existing_user = User.objects.filter(email=email).first()
        if existing_user:
            linked_social = SocialUser.objects.filter(user=existing_user, provider=Provider.KAKAO.value).exists()
            if not linked_social:
                raise ValidationError("이미 해당 이메일로 가입된 사용자가 존재합니다. 일반 로그인으로 시도해주세요.")
            raise ValidationError("이미 소셜 연결된 계정이 있습니다.")

        nickname = cast(str, user_info.get("nickname") or "")
        if User.objects.filter(nickname=nickname).exists():
            nickname = f"{nickname}_{User.objects.count() + 1}"

        if phone_number and User.objects.filter(phone_number=phone_number).exists():
            raise ValidationError("이미 등록된 휴대폰 번호입니다.")

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
            provider=Provider.KAKAO.value,
            provider_id=provider_id,
        )

        tokens = _issue_tokens(user)
        return {"detail": "카카오 로그인에 성공했습니다.", "data": tokens, "created": True}


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

        existing_user = User.objects.filter(email=email).first()
        if existing_user:
            linked_social = SocialUser.objects.filter(user=existing_user, provider=Provider.NAVER.value).exists()
            if not linked_social:
                raise ValidationError("이미 해당 이메일로 가입된 사용자가 존재합니다. 일반 로그인으로 시도해주세요.")
            raise ValidationError("이미 소셜 연결된 계정이 있습니다.")

        nickname = cast(str, user_info.get("nickname") or "")
        if User.objects.filter(nickname=nickname).exists():
            nickname = f"{nickname}_{User.objects.count() + 1}"

        if phone_number and User.objects.filter(phone_number=phone_number).exists():
            raise ValidationError("이미 등록된 휴대폰 번호입니다.")

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
        return {"detail": "네이버 로그인에 성공했습니다.", "data": tokens, "created": True}
