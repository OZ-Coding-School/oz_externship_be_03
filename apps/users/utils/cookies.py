from __future__ import annotations

from typing import Literal, Optional, cast

from django.conf import settings
from rest_framework.response import Response

SameSite = Optional[Literal["Lax", "Strict", "None", False]]
COOKIE_SAMESITE: SameSite = cast(SameSite, settings.AUTH_REFRESH_COOKIE_SAMESITE)


def set_refresh_cookie(resp: Response, refresh: str) -> None:
    resp.set_cookie(
        key=settings.AUTH_REFRESH_COOKIE_NAME,
        value=refresh,
        max_age=settings.AUTH_REFRESH_COOKIE_MAX_AGE,
        path=settings.AUTH_REFRESH_COOKIE_PATH,
        secure=settings.AUTH_REFRESH_COOKIE_SECURE,
        httponly=settings.AUTH_REFRESH_COOKIE_HTTPONLY,
        samesite=COOKIE_SAMESITE,
    )


def clear_refresh_cookie(resp: Response) -> None:
    resp.delete_cookie(
        key=settings.AUTH_REFRESH_COOKIE_NAME,
        path=settings.AUTH_REFRESH_COOKIE_PATH,
        samesite=COOKIE_SAMESITE,
    )
