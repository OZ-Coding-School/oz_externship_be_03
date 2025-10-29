from __future__ import annotations

from typing import Any, Dict, Optional, cast

from django.contrib.auth import authenticate
from django.core.cache import cache
from django.utils import timezone
from rest_framework_simplejwt.exceptions import ExpiredTokenError, TokenError
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.users.models.user import User as UserModel
from apps.users.utils.jwt import (
    ACCESS_DENYLIST_PREFIX,
    REFRESH_DENYLIST_PREFIX,
)


# -------------------------------------------------------------------
# 토큰 발급 유틸
# -------------------------------------------------------------------
def _issue_tokens(user: UserModel) -> Dict[str, str]:
    """
    주어진 사용자에 대한 access/refresh 페어 발급
    """
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


# -------------------------------------------------------------------
# 인증 + 토큰 발급
# -------------------------------------------------------------------
def authenticate_and_issue_tokens(*, email: str, password: str) -> Dict[str, str]:
    """
    - 기본: 이메일 기반 인증
    """
    identifier = (email or "").strip()

    # 1) 이메일 기반 인증
    user: Optional[UserModel] = authenticate(email=identifier, password=password)

    # 2) 실패 시 에러처리
    if user is None:
        raise PermissionError("존재하지 않는 계정이거나 비밀번호가 올바르지 않습니다.")

    if not getattr(user, "is_active", True):
        raise PermissionError("비활성화된 계정입니다.")

    return _issue_tokens(user)


# -------------------------------------------------------------------
# refresh → access 재발급
# -------------------------------------------------------------------
def refresh_access_token(*, refresh_token: str) -> str:
    """
    SimpleJWT refresh로 access 토큰 재발급
    """
    try:
        token = RefreshToken(cast(Any, refresh_token))
        return str(token.access_token)
    except ExpiredTokenError as e:
        raise PermissionError("만료된 refresh 토큰입니다.") from e
    except TokenError as e:
        raise PermissionError("유효하지 않은 refresh 토큰입니다.") from e


# -------------------------------------------------------------------
# 리프레시 토큰 캐시 denylist
# -------------------------------------------------------------------
def denylist_refresh_token_raw(refresh_raw: str) -> bool:
    """
    리프레시 토큰 문자열을 받아 만료 시점까지 캐시에 denylist 등록.
    """
    try:
        rt = RefreshToken(cast(Any, refresh_raw))
        jti = str(rt["jti"])
        exp = int(rt["exp"])
        ttl = max(exp - int(timezone.now().timestamp()), 0)
        if ttl > 0:
            cache.set(f"{REFRESH_DENYLIST_PREFIX}{jti}", True, ttl)
        return True
    except TokenError:
        return False


def is_refresh_denied(rt: RefreshToken) -> bool:
    """
    RefreshToken 객체가 캐시 denylist에 존재하는지 확인.
    """
    jti = str(rt["jti"])
    return bool(cache.get(f"{REFRESH_DENYLIST_PREFIX}{jti}"))


# -------------------------------------------------------------------
# 액세스 토큰 캐시 denylist
# -------------------------------------------------------------------
def denylist_access_token_raw(access_raw: str) -> bool:
    """
    액세스 토큰 문자열을 받아 만료 시점까지 캐시에 denylist 등록.
    """
    try:
        at = AccessToken(cast(Any, access_raw))
        jti = str(at["jti"])
        exp = int(at["exp"])
        ttl = max(exp - int(timezone.now().timestamp()), 0)
        if ttl > 0:
            cache.set(f"{ACCESS_DENYLIST_PREFIX}{jti}", True, ttl)
        return True
    except TokenError:
        return False


def is_access_denied(at: AccessToken) -> bool:
    """
    AccessToken 객체가 캐시 denylist에 존재하는지 확인.
    """
    jti = str(at["jti"])
    return bool(cache.get(f"{ACCESS_DENYLIST_PREFIX}{jti}"))
