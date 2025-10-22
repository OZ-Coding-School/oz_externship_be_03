from __future__ import annotations

import secrets
import string
import uuid
from typing import Any, Dict

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from rest_framework import status
from rest_framework.response import Response

from apps.users.enums import EmailVerificationPurpose
from apps.users.utils.verify_token import issue_verify_token
from config.settings.base import (
    ATTEMPT_LOCK_SECONDS,
    GLOBAL_LOCK_SECONDS,
    GLOBAL_MAX_FAILS,
    MAX_FAIL_ATTEMPTS,
    ONE_TIME_TTL_SECONDS,
    RESEND_COOLDOWN_SECONDS,
    VERIFY_TOKEN_EXPIRES_SECONDS,
)


# ---------------------------------------------------------------------
# 내부 유틸
# ---------------------------------------------------------------------
def _purpose_whitelist(purpose: str) -> bool:
    return purpose in EmailVerificationPurpose


def _normalize_email(raw: str) -> str:
    return (raw or "").strip().lower()


def _pending_key(email: str, purpose: str, request_id: str) -> str:
    return f"verify:email:pending:{email}:{purpose}:{request_id}"


def _lock_key(email: str, purpose: str) -> str:
    return f"verify:email:lock:{email}:{purpose}"


def _fail_key(email: str, purpose: str) -> str:
    return f"verify:email:failcnt:{email}:{purpose}"


def _rate_key(email: str) -> str:
    return f"ratelimit:email:send:{email}"


def _global_fail_key(email: str) -> str:
    return f"verify:email:failcnt:global:{email}"


def _global_lock_key(email: str) -> str:
    return f"verify:email:lock:global:{email}"


def _generate_code() -> str:
    # 6자리 숫자
    return "".join(secrets.choice(string.digits) for _ in range(6))


# ---------------------------------------------------------------------
# 발송
# ---------------------------------------------------------------------
def email_send_code(*, purpose: EmailVerificationPurpose, email: str) -> Response | Dict[str, Any]:
    """
    - 목적/이메일 검증
    - 레이트리밋(쿨다운)
    - 코드 생성 + request_id 생성(UUID)
    - pending 키에 (코드) 보관
    - 이메일 발송
    - 메타 반환
    """
    if not _purpose_whitelist(purpose):
        return Response(
            {"error": "요청한 목적은 이메일 인증에서 지원되지 않습니다."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    to = _normalize_email(email)
    if not to:
        return Response({"error": "이메일이 유효하지 않습니다."}, status=status.HTTP_400_BAD_REQUEST)

    rate_key = _rate_key(to)
    if cache.get(rate_key):
        return Response({"error": "재전송 대기 시간이 지나지 않았습니다."}, status=status.HTTP_429_TOO_MANY_REQUESTS)
    cache.set(rate_key, "1", timeout=RESEND_COOLDOWN_SECONDS)

    # 코드 & 요청 ID
    code = _generate_code()
    request_id = uuid.uuid4().hex  # Twilio SID 대체 개념

    # 보관: pending (목적/주체/요청ID 기준)
    cache.set(_pending_key(to, purpose, request_id), code, timeout=ONE_TIME_TTL_SECONDS)

    # 이메일 발송
    subject = "[Dr.True] 이메일 인증코드 안내"
    message = (
        f"요청 목적: {purpose}\n"
        f"인증코드: {code}\n"
        f"유효시간: {ONE_TIME_TTL_SECONDS}초\n"
        f"이 코드는 타인과 공유하지 마세요."
    )
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None)
    try:
        send_mail(subject, message, from_email, [to], fail_silently=False)
    except Exception as e:
        # 발송 실패 시 pending/쿨다운 정리
        cache.delete(_pending_key(to, purpose, request_id))
        cache.delete(rate_key)
        raise RuntimeError(f"이메일 인증코드 발송 실패: {e}")

    return {
        "request_id": request_id,
        "expires_in": ONE_TIME_TTL_SECONDS,
        "cooldown": RESEND_COOLDOWN_SECONDS,
        "max_attempts": MAX_FAIL_ATTEMPTS,
    }


# ---------------------------------------------------------------------
# 확인
# ---------------------------------------------------------------------
def email_confirm_code(
    *, purpose: EmailVerificationPurpose, email: str, verification_code: str, request_id: str
) -> Response | Dict[str, Any]:
    """
    - 목적/이메일 검증
    - 락 체크(글로벌/목적)
    - pending(요청ID)에 저장된 코드와 입력 코드 비교
    - 실패 시 카운트 증가/락
    - 성공 시 verify_token 발급 + 목적별 카운터/락 정리 + pending 제거
    """
    if not _purpose_whitelist(purpose):
        return Response(
            {"error": "요청한 목적은 이메일 인증에서 지원되지 않습니다."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    to = _normalize_email(email)
    if not to:
        return Response({"error": "이메일이 유효하지 않습니다."}, status=status.HTTP_400_BAD_REQUEST)

    # 잠금 확인
    lock_key_global = _global_lock_key(to)
    lock_key_purpose = _lock_key(to, purpose)
    if cache.get(lock_key_global) or cache.get(lock_key_purpose):
        return Response(
            {"error": "시도 제한 횟수를 초과했습니다. 잠시 뒤 다시 시도해주세요."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    # pending 매칭 확인
    pending_key = _pending_key(to, purpose, request_id)
    pending_code = cache.get(pending_key)
    if not pending_code:
        return Response({"error": "해당 목적에 대한 인증 요청이 없습니다."}, status=status.HTTP_404_NOT_FOUND)

    # 실패 카운터 키
    fail_key_global = _global_fail_key(to)
    fail_key_purpose = _fail_key(to, purpose)

    def _bump_fail_and_maybe_lock() -> None:
        # 글로벌 실패
        cache.add(fail_key_global, 0, timeout=GLOBAL_LOCK_SECONDS)
        gcnt = cache.incr(fail_key_global)
        if gcnt >= GLOBAL_MAX_FAILS:
            cache.set(lock_key_global, "1", timeout=GLOBAL_LOCK_SECONDS)
        # 목적별 실패
        cache.add(fail_key_purpose, 0, timeout=ATTEMPT_LOCK_SECONDS)
        pcnt = cache.incr(fail_key_purpose)
        if pcnt >= MAX_FAIL_ATTEMPTS:
            cache.set(lock_key_purpose, "1", timeout=ATTEMPT_LOCK_SECONDS)

    if str(pending_code) != str(verification_code):
        _bump_fail_and_maybe_lock()
        return Response({"error": "인증코드가 유효하지 않습니다."}, status=status.HTTP_400_BAD_REQUEST)

    # 성공: 검증 토큰 발급 (이메일 기준)
    verify_token = issue_verify_token(sub=to, to=to, purpose=purpose)

    cache.delete(fail_key_purpose)
    cache.delete(lock_key_purpose)
    cache.delete(pending_key)

    return {
        "verify_token": verify_token,
        "expires_in": VERIFY_TOKEN_EXPIRES_SECONDS,
    }
