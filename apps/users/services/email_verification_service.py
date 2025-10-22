from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from django.conf import settings
from django.core.cache import cache
from django.utils.crypto import get_random_string

# from apps.users.models.managers import _normalize_email

CODE_TTL_SEC: Final[int] = 60 * 10  # 인증코드 유효기간: 10분
VERIFIED_TTL_SEC: Final[int] = 60 * 10  # 인증완료 플래그: 10분


def _code_key(email: str, purpose: str) -> str:
    # ex) verify:code:signup:user%40example.com
    return f"verify:code:{purpose}:{email}"


def _verified_key(email: str, purpose: str) -> str:
    # ex) verify:done:signup:user%40example.com
    return f"verify:done:{purpose}:{email}"


@dataclass
class EmailVerificationService:
    """
    - 코드 검증 성공 시: mark_verified(email, purpose)
    - 가입 등 민감액션 전: consume_verified(email, purpose)로 1회성 소비
    """

    def issue_code(self, *, email: str, purpose: str, length: int = 6, ttl: int = CODE_TTL_SEC) -> str:
        """
        코드 발급: 숫자형 인증코드를 발급하고 TTL로 저장
        """
        code = get_random_string(length=length, allowed_chars="0123456789")
        cache.set(_code_key(email, purpose), code, timeout=ttl)
        return code

    def verify_code(self, *, email: str, purpose: str, code: str) -> bool:
        """
        코드 검증: 저장된 코드와 제출된 코드가 일치하는지 확인
        """
        saved = cache.get(_code_key(email, purpose))
        return str(saved) == str(code)

    def mark_verified(self, *, email: str, purpose: str, ttl: int = VERIFIED_TTL_SEC) -> None:
        """
        코드 검증 성공 시 호출: 완료 플래그를 TTL과 함께 저장
        """
        cache.set(_verified_key(email, purpose), "1", timeout=ttl)
        cache.delete(_code_key(email, purpose))

    def is_verified(self, *, email: str, purpose: str) -> bool:
        """
        완료 플래그가 현재 살아있는지만 조회(1회성 소비는 하지 않음)
        """
        key = _verified_key(email, purpose)
        return cache.get(key) is not None

    def consume_verified(self, *, email: str, purpose: str) -> bool:
        """
        인증완료 플래그를 '가져오며 삭제'(재사용 방지).
        """
        key = _verified_key(email, purpose)
        if cache.get(key) is not None:
            cache.delete(key)
            return True
        return False
