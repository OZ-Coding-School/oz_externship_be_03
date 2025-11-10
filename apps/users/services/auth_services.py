from __future__ import annotations

from typing import Any, Dict, Optional, cast

from django.contrib.auth import authenticate
from rest_framework_simplejwt.exceptions import ExpiredTokenError, TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.models.user import User as UserModel


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
