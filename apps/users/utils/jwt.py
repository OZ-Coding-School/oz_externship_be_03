from __future__ import annotations

from typing import Literal, Optional, Tuple, cast

from rest_framework.request import Request
from rest_framework_simplejwt.settings import api_settings

SameSite = Optional[Literal["Lax", "Strict", "None", False]]

# 캐시 Denylist 키 프리픽스
REFRESH_DENYLIST_PREFIX = "jwt:deny:refresh:"
ACCESS_DENYLIST_PREFIX = "jwt:deny:access:"


def coerce_samesite(value: object) -> SameSite:
    """
    - 허용: "Lax" | "Strict" | "None" | False
    - 그 외: None
    """
    if value in ("Lax", "Strict", "None"):
        return cast(SameSite, value)
    if value is False:
        return cast(SameSite, value)
    return None


def is_jwt_like(token: str) -> bool:
    parts = token.split(".")
    return len(parts) == 3 and all(p for p in parts)


def extract_bearer_token(request: Request) -> Optional[str]:
    """
    SIMPLE_JWT 설정(AUTH_HEADER_NAME / TYPES)에 맞춰 액세스 토큰 추출
    """
    header_name = api_settings.AUTH_HEADER_NAME
    header_types = tuple(t.lower() for t in api_settings.AUTH_HEADER_TYPES)

    raw = request.META.get(header_name, "") or request.headers.get("Authorization", "")
    if not raw:
        return None

    parts: Tuple[str, str] | None = None
    try:
        scheme, token = raw.split(" ", 1)
        parts = (scheme.strip().lower(), token.strip())
    except ValueError:
        return None

    if parts and parts[0] in header_types and parts[1]:
        return parts[1]
    return None
