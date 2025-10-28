from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.hashers import check_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.users.enums import PhoneVerificationPurpose
from apps.users.utils.verify_token import verify_and_consume  # Response | dict

if TYPE_CHECKING:
    from apps.users.models import User as UserModel

User = get_user_model()


def update_user_profile(
    *,
    user: UserModel,
    nickname: Optional[str],
    profile_img_url: Optional[str],
    phone_number: Optional[str],
    verify_token: Optional[str],
) -> UserModel:
    """
    - 닉네임/프로필 이미지만 오면 그대로 부분 수정
    - 휴대폰 변경이 포함되면: verify_token으로 목적/주체 검증 + 원타임 소비 후 저장
    - 중복은 본인 제외 기준
    """

    # 닉네임 중복(본인 제외)
    if nickname is not None and nickname != user.nickname:
        # 프로젝트 제공 매니저 사용
        if User.objects.exists_nickname(nickname):
            raise ValidationError({"error": "이미 사용 중인 닉네임입니다."})

    if phone_number is not None:
        # 이미 등록된 번호와 동일하면 차단
        if phone_number == user.phone_number:
            raise ValidationError({"error": "현재 등록된 휴대폰 번호와 동일합니다."})

        if not verify_token:
            raise ValidationError({"error": "휴대폰 번호 변경에는 verify_token이 필요합니다."})

        verify_and_consume(
            verify_token,
            expected_purpose=PhoneVerificationPurpose.CHANGE_PHONE,
            expected_sub=phone_number,
        )

        # 본인 제외 중복
        if User.objects.filter(is_active=True, phone_number=phone_number).exclude(pk=user.pk).exists():
            raise ValidationError({"error": "이미 사용 중인 휴대폰 번호입니다."})

    with transaction.atomic():
        user.nickname = nickname if nickname is not None else user.nickname
        user.profile_img_url = profile_img_url if profile_img_url is not None else user.profile_img_url
        user.phone_number = phone_number if phone_number is not None else user.phone_number
        user.save(update_fields=["nickname", "profile_img_url", "phone_number"])
    return user


def change_password(*, user: UserModel, current_password: str, new_password: str, new_password_confirm: str) -> None:
    """
    - 현재 비밀번호 확인
    - 새 비밀번호 = 새 비밀번호 확인
    - 새 비밀번호 != 현재 비밀번호
    - Django 비밀번호 정책 검사
    """

    # 현재 비밀번호 확인
    if not user.check_password(current_password):
        raise ValidationError({"error": "현재 비밀번호가 올바르지 않습니다."})

    # 새 비밀번호 = 새 비밀번호 확인
    if new_password != new_password_confirm:
        raise ValidationError({"error": "새 비밀번호와 확인 비밀번호가 일치하지 않습니다."})

    # 새 비밀번호 != 현재 비밀번호
    if check_password(new_password, user.password):
        raise ValidationError({"error": "새 비밀번호는 이전 비밀번호와 달라야 합니다."})

    # Django 비밀번호 정책 검사
    try:
        password_validation.validate_password(new_password, user=user)
    except DjangoValidationError as e:
        raise ValidationError({"error": str(e.messages[0])})

    # 5) 적용
    user.set_password(new_password)
    user.save(update_fields=["password"])
