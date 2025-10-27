from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from rest_framework.exceptions import APIException, ValidationError

from apps.users.enums import Role
from apps.users.models.user import User as UserModel
from apps.users.serializers.user_signup_serializers import SignupPayload
from apps.users.validators import (
    validate_birthday,
    validate_korean_phone,
    validate_name,
    validate_nickname,
)

User = get_user_model()


# ===========================================
# 유틸 함수
# ===========================================
def role_from_flags(*, is_staff: bool, is_superuser: bool) -> str:
    if is_superuser:
        return Role.ADMIN.value
    if is_staff:
        return Role.STAFF.value
    return Role.USER.value


def flags_from_role(role: str) -> dict[str, bool]:
    if role == Role.ADMIN.value:
        return {"is_staff": True, "is_superuser": True}
    if role == Role.STAFF.value:
        return {"is_staff": True, "is_superuser": False}
    return {"is_staff": False, "is_superuser": False}


def status_from_active(is_active: bool) -> str:
    return "active" if is_active else "inactive"


def active_from_status(status: str) -> bool:
    return status == "active"


# ===========================================
# 에러 헬퍼 함수
# ===========================================
def _extract_msgs(exc: Exception) -> list[str]:
    """
    DRF/Django ValidationError 호환 에러 메시지 리스트화.
    detail/message_dict/messages 우선 사용, 없으면 str(exc).
    """
    detail = getattr(exc, "detail", None)
    if isinstance(detail, dict):
        out: list[str] = []
        for v in detail.values():
            if isinstance(v, list):
                out.extend(map(str, v))
            else:
                out.append(str(v))
        return out
    if isinstance(detail, list):
        return [str(x) for x in detail]
    if detail is not None:
        return [str(detail)]

    message_dict = getattr(exc, "message_dict", None)
    if isinstance(message_dict, dict):
        out2: list[str] = []
        for v in message_dict.values():
            if isinstance(v, list):
                out2.extend(map(str, v))
            else:
                out2.append(str(v))
        return out2

    messages = getattr(exc, "messages", None)
    if isinstance(messages, list):
        return [str(x) for x in messages]

    return [str(exc)]


def _map_integrity_error_to_conflicts(exc: IntegrityError) -> dict[str, list[str]]:
    """
    DB 제약 위반(유니크 등)을 필드별 메시지로 매핑.
    """
    msg = str(exc).lower()
    conflict_map: dict[str, list[str]] = {}

    # 이메일
    if any(k in msg for k in ["email", "users_email_key", "unique_email"]):
        conflict_map.setdefault("email", []).append("이미 사용 중인 이메일입니다.")

    # 휴대폰 번호
    if any(k in msg for k in ["phone", "phone_number", "users_phone_number_key", "unique_phone"]):
        conflict_map.setdefault("phone_number", []).append("이미 사용 중인 휴대폰 번호입니다.")

    # 닉네임
    if any(k in msg for k in ["nickname", "users_nickname_key", "unique_nickname", "nick"]):
        conflict_map.setdefault("nickname", []).append("이미 사용 중인 닉네임입니다.")

    if not conflict_map:
        conflict_map["non_field_errors"] = ["중복된 값이 존재합니다."]

    return conflict_map


# ===========================================
# Signup Service
# ===========================================
@dataclass
class DefaultSignupService:
    """
    회원가입 처리 서비스
    """

    @transaction.atomic
    def sign_up(self, payload: SignupPayload) -> UserModel:
        # ---- 입력 추출
        email: str = payload["email"]
        phone_number: str = payload["phone_number"]
        nickname: str = payload["nickname"]
        password: str = payload["password"]
        name: str = payload["name"]
        birthday = payload["birthday"]
        gender = payload.get("gender")

        # ---- 역할 → 권한 플래그
        flags = flags_from_role(payload.get("role", Role.USER))

        # ---- 필드 검증
        errors_map: dict[str, list[str]] = {}
        validators: list[tuple[str, Any, Any]] = [
            ("nickname", validate_nickname, nickname),
            ("name", validate_name, name),
            ("phone_number", validate_korean_phone, phone_number),
        ]
        for field_name, validator, value in validators:
            try:
                validator(value)
            except Exception as exc:
                errors_map.setdefault(field_name, []).extend(_extract_msgs(exc))

        try:
            validate_birthday(birthday)
        except Exception as exc:
            errors_map.setdefault("birthday", []).extend(_extract_msgs(exc))

        if errors_map:
            raise ValidationError(detail=errors_map)

        # ---- 유저 생성
        try:
            user = User.objects.create_user(
                email=email,  # UserManager에서 도메인만 소문자화
                password=password,
                nickname=nickname,
                name=name,
                phone_number=phone_number,
                birthday=birthday,
                gender=gender,
                is_staff=flags["is_staff"],
                is_superuser=flags["is_superuser"],
                is_active=True,
            )
        except IntegrityError as exc:
            conflict_map = _map_integrity_error_to_conflicts(exc)
            api_exc = APIException(detail=conflict_map)
            api_exc.status_code = 409
            raise api_exc

        return user
