from __future__ import annotations

from typing import Optional

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import AuthenticationFailed, Throttled, ValidationError

User = get_user_model()

# 멱등 & 레이트리밋
IDEMPOTENCY_TTL_SECONDS = 10 * 60
RATE_LIMIT_SECONDS = 5


def reset_password(
    *,
    claims: dict[str, str | int | None],
    new_password: str,
    new_password_confirm: str,
    idempotency_key: Optional[str] = None,
) -> None:
    """
    퍼미션이 검증/소비한 토큰의 claims를 받아 비밀번호를 재설정
    """
    # 같은 키로 이미 성공했으면 no-op
    if idempotency_key:
        ikey = f"idemp:password-reset:{idempotency_key}"
        if cache.get(ikey) == "OK":
            return

    # 레이트 리밋 (클레임의 jti/subject 기반)
    jti = str(claims.get("jti") or "")
    rl_key = f"ratelimit:password-reset:{jti}" if jti else None
    if rl_key and cache.get(rl_key):
        raise Throttled(5, {"error": "요청 한도가 초과되었습니다. 잠시 후 다시 시도해 주세요."})
    if rl_key:
        cache.set(rl_key, "1", timeout=RATE_LIMIT_SECONDS)

    # 비밀번호 일치 확인
    if new_password != new_password_confirm:
        raise ValidationError({"error": "비밀번호 확인이 일치하지 않습니다."})

    # 사용자 조회
    subject = str(claims.get("sub") or "")
    if not subject:
        raise AuthenticationFailed({"error": "토큰이 유효하지 않습니다."})

    try:
        user = User.objects.get(phone_number=subject, is_active=True)
    except User.DoesNotExist:
        raise AuthenticationFailed({"error": "토큰이 유효하지 않습니다."})

    # Django 기본 비밀번호 정책 검사
    try:
        validate_password(password=new_password, user=user)
    except DjangoValidationError as e:
        msgs = list(e.messages)
        raise ValidationError({"error": msgs[0] if msgs else "비밀번호 정책 위반"})

    # 저장
    user.set_password(new_password)
    user.save(update_fields=["password"])

    # 멱등 성공 마킹
    if idempotency_key:
        cache.set(ikey, "OK", timeout=IDEMPOTENCY_TTL_SECONDS)
