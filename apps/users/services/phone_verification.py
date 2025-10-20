from __future__ import annotations

import os
import re
from typing import Any, Literal, Optional

from django.core.cache import cache
from twilio.rest import Client  # type: ignore

Purpose = Literal["signup", "find_email", "change_phone", "reset_password"]

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_VERIFY_SERVICE_SID = os.getenv("TWILIO_VERIFY_SERVICE_SID", "")


_twilio: Any = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

ONE_TIME_TTL_SECONDS = 10 * 60  # 10분
RESEND_COOLDOWN_SECONDS = 60  # 재전송 쿨다운
ATTEMPT_LOCK_SECONDS = 10 * 60  # 과도한 실패 잠금
MAX_FAIL_ATTEMPTS = 5


def _purpose_whitelist(purpose: str) -> bool:
    return purpose in {"signup", "find_email", "change_phone", "reset_password"}


def _normalize_kr_phone(raw: str) -> str:
    """
    내부 전용 정규화:
    - 입력: 010-1234-5678, +82 10 1234 5678, 821012345678, 01012345678 등
    - 출력: +8210XXXXXXXX (E.164)
    - 대한민국(82) 번호만 허용. 010으로 시작하는 휴대폰만 허용.
    """
    if not raw:
        raise ValueError("휴대폰 번호를 입력해 주세요.")
    digits = re.sub(r"\D", "", raw)

    # 82 프리픽스/0 리드 제거
    if digits.startswith("82"):
        local = digits[2:]  # e.g. 10XXXXXXXX
    elif digits.startswith("0"):
        local = digits[1:]  # e.g. 10XXXXXXXX
    else:
        # +8210..., 8210..., 010... 외 형태는 거절
        raise ValueError("대한민국 휴대폰 번호 형식만 지원합니다. 예) 01012345678")

    # 010 휴대폰 패턴만 허용: 10 + 8자리 = 총 10자리
    if not re.fullmatch(r"10\d{8}", local):
        raise ValueError("휴대폰 번호 형식이 올바르지 않습니다. 예) 01012345678")

    return f"+82{local}"


def _ensure_twilio_verify_ready() -> None:
    if not TWILIO_VERIFY_SERVICE_SID:
        raise RuntimeError("Twilio Verify 서비스 SID가 설정되지 않았습니다.")


def send_code(*, purpose: Purpose, phone_number: str) -> None:
    if not _purpose_whitelist(purpose):
        raise ValueError("Invalid purpose")

    _ensure_twilio_verify_ready()
    to = _normalize_kr_phone(phone_number)

    # 레이트 리밋: 60초 이내 중복 전송 방지
    rate_key = f"ratelimit:phone:send:{to}"
    if cache.get(rate_key):
        raise RuntimeError("Too Many Requests")
    cache.set(rate_key, "1", timeout=RESEND_COOLDOWN_SECONDS)

    # Twilio Verify: 코드 전송
    _twilio.verify.v2.services(TWILIO_VERIFY_SERVICE_SID).verifications.create(to=to, channel="sms")


def confirm_code(*, purpose: Purpose, phone_number: str, code: str, user_id: Optional[int] = None) -> None:
    if not _purpose_whitelist(purpose):
        raise ValueError("Invalid purpose")

    _ensure_twilio_verify_ready()
    to = _normalize_kr_phone(phone_number)

    # 시도 제한: 5회 실패 시 10분 락
    lock_key = f"verify:phone:lock:{to}:{purpose}"
    fail_key = f"verify:phone:failcnt:{to}:{purpose}"
    if cache.get(lock_key):
        raise RuntimeError("Locked due to too many attempts")

    # Twilio Verify: 코드 검증
    check = _twilio.verify.v2.services(TWILIO_VERIFY_SERVICE_SID).verification_checks.create(to=to, code=code)

    if getattr(check, "status", None) != "approved":
        # 실패 카운터: 최초 생성 + TTL → 이후 증가
        cache.add(fail_key, 0, timeout=ATTEMPT_LOCK_SECONDS)  # 없을 때만 생성
        cnt = cache.incr(fail_key)

        if cnt >= MAX_FAIL_ATTEMPTS:
            cache.set(lock_key, "1", timeout=ATTEMPT_LOCK_SECONDS)
        raise RuntimeError("Invalid code")

    # 성공 → 퍼미션이 소비할 원타임 키 세팅
    subject = str(user_id) if user_id is not None else phone_number
    ok_key = f"verify:phone:{subject}:{purpose}"
    cache.set(ok_key, to, timeout=ONE_TIME_TTL_SECONDS)

    # 실패 카운터/락 초기화
    cache.delete(fail_key)
    cache.delete(lock_key)
