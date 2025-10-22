from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Type, cast

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from rest_framework.exceptions import APIException, ValidationError

from apps.users.enums import Role
from apps.users.managers.managers import UserManager
from apps.users.models.user import User as UserType
from apps.users.serializers.user_signup_serializers import SignupPayload
from apps.users.services.email_verification_service import EmailVerificationService
from apps.users.validators import (
    validate_korean_phone,
    validate_name,
    validate_nickname,
)

# ===========================================
# Constants & Utilities
# ===========================================
email_svc = EmailVerificationService()
UserModel = get_user_model()
mgr: UserManager = UserModel.objects


# ===========================================
# Enum flag utilities
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
# Signup Service
# ===========================================
@dataclass
class DefaultSignupService:
    """회원가입 처리 서비스"""

    @transaction.atomic
    def sign_up(self, payload: SignupPayload) -> UserType:
        email = payload["email"]
        phone_number = payload["phone_number"]
        nickname = payload["nickname"]
        password = payload["password"]
        name = payload["name"]
        birthday = payload["birthday"]  # str | date | datetime 허용
        gender = payload["gender"]
        role = cast(str, payload.get("role", Role.USER.value))
        flags = flags_from_role(role)

        # --------------------------
        # (1) Validation - 400 Bad Request
        # --------------------------
        errors_map: dict[str, list[str]] = {}

        for field_name, validator, value in [
            ("nickname", validate_nickname, nickname),
            ("name", validate_name, name),
            ("phone_number", validate_korean_phone, phone_number),
        ]:
            try:
                validator(value)
            except Exception as exc:
                for msg in _extract_msgs(exc):
                    errors_map.setdefault(field_name, []).append(msg)

        # 생년월일 변환 및 검증
        bday_parsed: date | None = None
        if isinstance(birthday, datetime):
            bday_parsed = birthday.date()
        elif isinstance(birthday, date):
            bday_parsed = birthday
        elif isinstance(birthday, str):
            try:
                bday_parsed = date.fromisoformat(birthday.strip())
            except ValueError:
                errors_map.setdefault("birthday", []).append("생년월일 형식이 올바르지 않습니다. 예) 1990-06-06")
        else:
            errors_map.setdefault("birthday", []).append("생년월일 형식이 올바르지 않습니다. 예) 1990-06-06")

        if bday_parsed and bday_parsed > date.today():
            errors_map.setdefault("birthday", []).append("생년월일은 미래일 수 없습니다.")

        if errors_map:
            raise ValidationError(detail=errors_map)

        # --------------------------
        # (2) Email verification - 422
        # --------------------------
        if not email_svc.consume_verified(email=email, purpose="signup"):
            ex = APIException(detail={"email": ["이메일 인증을 완료해주세요."]})
            ex.status_code = 422
            raise ex
        # --------------------------
        # (3) Create user - 409 Conflict
        # --------------------------
        try:
            user = mgr.create_user(
                email=email,
                password=password,
                nickname=nickname,
                name=name,
                phone_number=phone_number,
                birthday=bday_parsed,
                gender=gender,
                is_staff=flags["is_staff"],
                is_superuser=flags["is_superuser"],
                is_active=True,
            )
        except IntegrityError as exc:
            msg = str(exc).lower()
            conflict_map: dict[str, list[str]] = {}

            if "email" in msg or "users_email_key" in msg:
                conflict_map.setdefault("email", []).append("이미 사용 중인 이메일입니다.")
            if "phone" in msg or "phone_number" in msg or "users_phone_number_key" in msg:
                conflict_map.setdefault("phone_number", []).append("이미 사용 중인 휴대폰 번호입니다.")
            if "nickname" in msg or "users_nickname_key" in msg or "nick" in msg:
                conflict_map.setdefault("nickname", []).append("이미 사용 중인 닉네임입니다.")

            if not conflict_map:
                conflict_map["non_field_errors"] = ["중복된 값이 존재합니다."]

            ex = APIException(detail=conflict_map)
            ex.status_code = 409
            raise ex
            # raise Conflict(conflict_map)

        return user


# ===========================================
# Error extraction helper
# ===========================================
def _extract_msgs(exc: Exception) -> list[str]:
    """DRF/Django ValidationError 메시지를 리스트로 평탄화"""
    detail = getattr(exc, "detail", None)
    if isinstance(detail, dict):
        out: list[str] = []
        for v in detail.values():
            out.extend([str(x) for x in v]) if isinstance(v, list) else out.append(str(v))
        return out
    if isinstance(detail, list):
        return [str(x) for x in detail]
    if detail is not None:
        return [str(detail)]

    message_dict = getattr(exc, "message_dict", None)
    if isinstance(message_dict, dict):
        out_2: list[str] = []
        for v in message_dict.values():
            out_2.extend([str(x) for x in v]) if isinstance(v, list) else out_2.append(str(v))
        return out_2

    messages = getattr(exc, "messages", None)
    if isinstance(messages, list):
        return [str(x) for x in messages]

    return [str(exc)]
