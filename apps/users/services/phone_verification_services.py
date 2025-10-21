from __future__ import annotations

from typing import Any, Dict

from django.conf import settings
from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response
from twilio.rest import Client  # type: ignore

from apps.users.enums import PhoneVerificationPurpose
from apps.users.utils.verify_token import issue_verify_token
from apps.users.validators import validate_korean_phone
from config.settings.base import (
    ATTEMPT_LOCK_SECONDS,
    GLOBAL_LOCK_SECONDS,
    GLOBAL_MAX_FAILS,
    MAX_FAIL_ATTEMPTS,
    ONE_TIME_TTL_SECONDS,
    RESEND_COOLDOWN_SECONDS,
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_VERIFY_SERVICE_SID,
    VERIFY_TOKEN_EXPIRES_SECONDS,
)

_twilio: Any = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def _purpose_whitelist(purpose: str) -> bool:
    return purpose in PhoneVerificationPurpose


def _ensure_twilio_verify_ready() -> None:
    if not TWILIO_VERIFY_SERVICE_SID:
        raise RuntimeError("Twilio Verify 서비스 SID가 설정되지 않았습니다.")


def _normalize_kr_phone(raw: str) -> str:
    """
    입력: '010XXXXXXXX' (validate_korean_phone로 검증)
    출력: '+8210XXXXXXXX' (E.164)
    """
    validate_korean_phone(raw)
    return f"+82{raw[1:]}"


def _pending_key(subject: str, purpose: str, sid: str) -> str:
    return f"verify:phone:pending:{subject}:{purpose}:{sid}"


def _lock_key(to: str, purpose: str) -> str:
    return f"verify:phone:lock:{to}:{purpose}"


def _fail_key(to: str, purpose: str) -> str:
    return f"verify:phone:failcnt:{to}:{purpose}"


def _rate_key(to: str) -> str:
    return f"ratelimit:phone:send:{to}"


# 글로벌(번호 단위) 제한 키
def _global_fail_key(to_e164: str) -> str:
    return f"verify:phone:failcnt:global:{to_e164}"


def _global_lock_key(to_e164: str) -> str:
    return f"verify:phone:lock:global:{to_e164}"


def send_code(*, purpose: PhoneVerificationPurpose, phone_number: str) -> Response | Dict[str, Any]:
    """
    - 목적/번호 검증
    - 레이트리밋
    - Twilio Verify verifications.create → SID 획득
    - pending 키를 SID 단위로 생성
    - 메타 반환 (request_id = SID)
    """

    if not _purpose_whitelist(purpose):
        return Response(
            {"error": "요청한 목적은 휴대폰 인증에서 지원되지 않습니다."}, status=status.HTTP_400_BAD_REQUEST
        )

    _ensure_twilio_verify_ready()
    to = _normalize_kr_phone(phone_number)

    # 레이트 리밋: 60초 이내 중복 전송 방지
    rate_key = _rate_key(to)
    if cache.get(rate_key):
        return Response({"error": "재전송 대기 시간이 지나지 않았습니다."}, status=status.HTTP_429_TOO_MANY_REQUESTS)
    cache.set(rate_key, "1", timeout=RESEND_COOLDOWN_SECONDS)

    # Twilio Verify: 코드 전송 & SID 추출
    try:
        verification = _twilio.verify.v2.services(TWILIO_VERIFY_SERVICE_SID).verifications.create(to=to, channel="sms")
        sid = getattr(verification, "sid", None)
    except Exception as e:
        raise RuntimeError(f"Twilio 인증 요청 실패: {e}")
    sid = getattr(verification, "sid", None)

    if not sid:
        raise RuntimeError({"error": "인증코드 전송에 실패했습니다."})

    # 목적/주체 바인딩: 발송 대기 마커 (SID별로 분리)
    cache.set(_pending_key(subject=phone_number, purpose=purpose, sid=sid), to, timeout=ONE_TIME_TTL_SECONDS)

    return {
        "request_id": sid,
        "expires_in": ONE_TIME_TTL_SECONDS,
        "cooldown": RESEND_COOLDOWN_SECONDS,
        "max_attempts": MAX_FAIL_ATTEMPTS,
    }


def confirm_code(
    *, purpose: PhoneVerificationPurpose, phone_number: str, code: str, request_id: str
) -> Response | Dict[str, Any]:
    """
    - 목적/번호 검증
    - SID 바인딩 확인 (pending 키 존재 여부)
    - 실패 시 글로벌/목적 카운트 동시 증가, 임계치 도달 시 락
    - Twilio Verify verification_checks.create(verification_sid=..., code=...)
    - 성공 시 검증 토큰 발급(sub = E.164) + 카운터/락/대기키 정리
    """

    if not _purpose_whitelist(purpose):
        return Response(
            {"error": "요청한 목적은 휴대폰 인증에서 지원되지 않습니다."}, status=status.HTTP_400_BAD_REQUEST
        )

    _ensure_twilio_verify_ready()
    to = _normalize_kr_phone(phone_number)

    # 잠금 확인
    lock_key_global = _global_lock_key(to)
    lock_key_purpose = _lock_key(to, purpose)
    if cache.get(lock_key_global) or cache.get(lock_key_purpose):
        return Response(
            {"error": "시도 제한 횟수를 초과했습니다. 잠시 뒤 다시 시도해주세요."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    # 목적/주체/SID 매칭 확인
    pending_key = _pending_key(subject=phone_number, purpose=purpose, sid=request_id)
    if cache.get(pending_key) != to:
        # 해당 목적에 대한 발송 요청 자체가 없거나, 주체/번호가 불일치
        return Response({"error": "해당 목적에 대한 인증 요청이 없습니다."}, status=status.HTTP_404_NOT_FOUND)

    # 실패 카운터 키
    fail_key_global = _global_fail_key(to)
    fail_key_purpose = _fail_key(to, purpose)

    def _bump_fail_and_maybe_lock() -> None:
        # 글로벌 실패 증가 및 락 여부
        cache.add(fail_key_global, 0, timeout=GLOBAL_LOCK_SECONDS)
        gcnt = cache.incr(fail_key_global)
        if gcnt >= GLOBAL_MAX_FAILS:
            cache.set(lock_key_global, "1", timeout=GLOBAL_LOCK_SECONDS)

        # 목적별 실패 증가 및 락 여부
        cache.add(fail_key_purpose, 0, timeout=ATTEMPT_LOCK_SECONDS)
        pcnt = cache.incr(fail_key_purpose)
        if pcnt >= MAX_FAIL_ATTEMPTS:
            cache.set(lock_key_purpose, "1", timeout=ATTEMPT_LOCK_SECONDS)

    # Twilio Verify: 코드 검증
    try:
        check = _twilio.verify.v2.services(TWILIO_VERIFY_SERVICE_SID).verification_checks.create(
            verification_sid=request_id,
            code=code,
        )
    except Exception:
        _bump_fail_and_maybe_lock()
        return Response({"error": "인증코드 검증 중 오류가 발생했습니다."}, status=status.HTTP_400_BAD_REQUEST)

    if getattr(check, "status", None) != "approved":
        _bump_fail_and_maybe_lock()
        return Response({"error": "인증코드가 유효하지 않습니다."}, status=status.HTTP_400_BAD_REQUEST)

    # 성공: 검증 토큰 발급 (1회성)
    verify_token = issue_verify_token(sub=phone_number, to=to, purpose=purpose)

    # 정리: 목적별 실패/락 초기화, pending 제거
    cache.delete(fail_key_purpose)
    cache.delete(lock_key_purpose)
    # 글로벌 카운터/락은 정책에 따라 유지
    cache.delete(pending_key)

    return {
        "verify_token": verify_token,
        "expires_in": VERIFY_TOKEN_EXPIRES_SECONDS,
    }
