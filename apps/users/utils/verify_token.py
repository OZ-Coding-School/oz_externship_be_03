from __future__ import annotations

import time
import uuid
from typing import Any, Literal, TypedDict

import jwt
from django.conf import settings
from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response

from apps.users.enums import EmailVerificationPurpose, PhoneVerificationPurpose

REDIS_JTI_PREFIX = "verify:jti:"


def issue_verify_token(*, sub: str, to: str, purpose: PhoneVerificationPurpose | EmailVerificationPurpose) -> str:
    now = int(time.time())
    jti = uuid.uuid4().hex
    exp = now + settings.VERIFY_TOKEN_EXPIRES_SECONDS
    claims: dict[str, Any] = {"sub": sub, "to": to, "purpose": purpose, "jti": jti, "exp": exp}
    token = jwt.encode(claims, settings.VERIFY_TOKEN_SECRET, algorithm=settings.VERIFY_TOKEN_ALGO)
    cache.set(f"{REDIS_JTI_PREFIX}{jti}", "1", timeout=settings.VERIFY_TOKEN_EXPIRES_SECONDS)
    return token


def verify_and_consume(
    token: str,
    *,
    expected_purpose: PhoneVerificationPurpose | EmailVerificationPurpose,
    expected_sub: str | None = None,
) -> dict[str, Any] | Response:
    try:
        decoded: dict[str, Any] = jwt.decode(
            token, settings.VERIFY_TOKEN_SECRET, algorithms=[settings.VERIFY_TOKEN_ALGO]
        )
    except jwt.ExpiredSignatureError:
        return Response({"error": "검증 토큰이 유효하지 않거나 만료되었습니다."}, status=status.HTTP_401_UNAUTHORIZED)
    except jwt.InvalidTokenError:
        return Response({"error": "검증 토큰이 유효하지 않거나 만료되었습니다."}, status=status.HTTP_401_UNAUTHORIZED)

    claims: dict[str, Any] = {
        "sub": str(decoded.get("sub")),
        "to": str(decoded.get("to")),
        "purpose": decoded.get("purpose"),
        "jti": str(decoded.get("jti")),
        "exp": decoded.get("exp"),
    }

    if claims["purpose"] != expected_purpose:
        return Response({"error": "검증 토큰이 유효하지 않거나 만료되었습니다."}, status=status.HTTP_401_UNAUTHORIZED)
    if expected_sub is not None and claims["sub"] != expected_sub:
        return Response({"error": "검증 토큰이 유효하지 않거나 만료되었습니다."}, status=status.HTTP_401_UNAUTHORIZED)

    jti_key = f"{REDIS_JTI_PREFIX}{claims['jti']}"
    if not cache.get(jti_key):
        return Response({"error": "검증 토큰이 유효하지 않거나 만료되었습니다."}, status=status.HTTP_401_UNAUTHORIZED)
    cache.delete(jti_key)
    return claims
