from __future__ import annotations

import hmac
import time
import uuid
from typing import Any, Optional

import jwt
from django.conf import settings
from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response

from apps.users.enums import EmailVerificationPurpose, PhoneVerificationPurpose

REDIS_JTI_PREFIX = "verify:jti"
REDIS_USED_PREFIX = "verify:used"


def _serialize_purpose(purpose: Any) -> str:
    return getattr(purpose, "value", str(purpose))


def _jti_key(purpose: str, jti: str) -> str:
    # purpose 포함: 이메일/휴대폰 토큰 간 간섭 차단
    return f"{REDIS_JTI_PREFIX}:{purpose}:{jti}"


def _used_key(jti: str) -> str:
    return f"{REDIS_USED_PREFIX}:{jti}"


def _strip_bearer(token: str) -> str:
    t = token.strip()
    return t[7:].strip() if t.lower().startswith("bearer ") else t


def _safe_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(str(a), str(b))


def _now() -> int:
    return int(time.time())


def _build_verify_claims(*, sub: str, to: str, purpose: Any, ttl: int) -> dict[str, Any]:
    now = _now()
    jti = uuid.uuid4().hex
    exp = now + int(ttl)

    return {
        "sub": sub,
        "to": to,
        "purpose": _serialize_purpose(purpose),
        "jti": jti,
        "exp": exp,
        "iat": now,
    }


def issue_verify_token(
    *,
    sub: str,
    to: str,
    purpose: PhoneVerificationPurpose | EmailVerificationPurpose,
) -> str:
    ttl = getattr(settings, "VERIFY_TOKEN_EXPIRES_SECONDS", 600)
    algo = getattr(settings, "VERIFY_TOKEN_ALGO", "HS256")
    secret = getattr(settings, "VERIFY_TOKEN_SECRET")

    claims = _build_verify_claims(sub=sub, to=to, purpose=purpose, ttl=ttl)
    token = jwt.encode(claims, secret, algorithm=algo)

    key = _jti_key(claims["purpose"], claims["jti"])
    cache.set(key, 1, timeout=claims["exp"] - claims["iat"])

    return token


def verify_and_consume(
    token: str,
    *,
    expected_purpose: PhoneVerificationPurpose | EmailVerificationPurpose,
    expected_sub: Optional[str] = None,
) -> dict[str, Any] | Response:
    algo = getattr(settings, "VERIFY_TOKEN_ALGO", "HS256")
    secret = getattr(settings, "VERIFY_TOKEN_SECRET")

    token = _strip_bearer(token)

    try:
        decoded: dict[str, Any] = jwt.decode(token, secret, algorithms=[algo])
    except jwt.ExpiredSignatureError:
        return Response({"error": "검증 토큰이 유효하지 않거나 만료되었습니다."}, status=status.HTTP_401_UNAUTHORIZED)
    except jwt.InvalidTokenError:
        return Response({"error": "검증 토큰이 유효하지 않거나 만료되었습니다."}, status=status.HTTP_401_UNAUTHORIZED)

    claims: dict[str, Any] = {
        "sub": str(decoded.get("sub", "")),
        "to": str(decoded.get("to", "")),
        "purpose": _serialize_purpose(decoded.get("purpose")),
        "jti": str(decoded.get("jti", "")),
        "exp": int(decoded.get("exp", 0)),
        "iat": int(decoded.get("iat", 0)) if decoded.get("iat") else None,
    }

    # purpose 일치
    if not _safe_eq(claims["purpose"], _serialize_purpose(expected_purpose)):
        return Response({"error": "검증 토큰이 유효하지 않거나 만료되었습니다."}, status=status.HTTP_401_UNAUTHORIZED)

    # sub 일치 확인
    if expected_sub is not None and not _safe_eq(claims["sub"], expected_sub):
        return Response({"error": "검증 토큰이 유효하지 않거나 만료되었습니다."}, status=status.HTTP_401_UNAUTHORIZED)

    key = _jti_key(claims["purpose"], claims["jti"])

    if not cache.get(key):
        return Response({"error": "검증 토큰이 유효하지 않거나 만료되었습니다."}, status=status.HTTP_401_UNAUTHORIZED)

    # 재사용 방지: 이미 사용된 jti면 실패
    if not cache.add(_used_key(claims["jti"]), 1, timeout=60):
        return Response({"error": "검증 토큰이 유효하지 않거나 만료되었습니다."}, status=status.HTTP_401_UNAUTHORIZED)

    # 소비 완료
    cache.delete(key)
    return claims
