from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.exceptions import AuthenticationFailed, ValidationError

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
            if nickname is not None:
                user.nickname = nickname
            if profile_img_url is not None:
                user.profile_img_url = profile_img_url
            user.phone_number = phone_number
            user.save(update_fields=["nickname", "profile_img_url", "phone_number"])
        return user

    # 휴대폰 제외 일반 필드만 - 변경된 필드만 데이터베이스에 반영
    dirty: list[str] = []
    if nickname is not None:
        user.nickname = nickname
        dirty.append("nickname")
    if profile_img_url is not None:
        user.profile_img_url = profile_img_url
        dirty.append("profile_img_url")
    if dirty:
        user.save(update_fields=dirty)
    return user
