from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.hashers import check_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.core.exceptions import Conflict
from apps.core.utils.s3_uploader import S3Uploader
from apps.users.enums import PhoneVerificationPurpose
from apps.users.utils.verify_token import verify_and_consume  # Response | dict

if TYPE_CHECKING:
    from apps.users.models import User as UserModel

User = get_user_model()

logger = logging.getLogger(__name__)


def _extract_key_from_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    base = S3Uploader.S3_BASE_URL
    return url[len(base) :] if url.startswith(base) else None


def update_user_profile(
    *,
    user: UserModel,
    nickname: Optional[str],
    profile_img: Optional[Any],
    phone_number: Optional[str],
    phone_verify_token: Optional[str],
) -> UserModel:
    """
    - 닉네임/프로필 이미지만 오면 그대로 부분 수정
    - 휴대폰 변경이 포함되면: verify_token으로 목적/주체 검증 + 원타임 소비 후 저장
    - 중복은 본인 제외 기준
    """

    # 닉네임 중복 채크
    if nickname:
        if nickname == user.nickname:
            raise Conflict({"error": "현재 사용 중인 닉네임과 동일합니다."})
        if User.objects.exists_nickname(nickname):
            raise Conflict({"error": "이미 사용 중인 닉네임입니다."})

    if phone_number is not None:
        # 이미 등록된 번호와 동일하면 차단
        if phone_number == user.phone_number:
            raise Conflict({"error": "현재 등록된 휴대폰 번호와 동일합니다."})

        if not phone_verify_token:
            raise ValidationError({"error": "휴대폰 번호 변경에는 verify_token이 필요합니다."})

        verify_and_consume(
            phone_verify_token,
            expected_purpose=PhoneVerificationPurpose.CHANGE_PHONE,
            expected_sub=phone_number,
        )

        # 중복 번호 체크
        if User.objects.exists_phone(phone_number):
            raise Conflict({"error": "이미 사용 중인 휴대폰 번호입니다."})

    # 새 이미지가 있다면, 우선 업로드
    new_profile_url: Optional[str] = None
    uploaded_new_key: Optional[str] = None
    old_key_to_delete: Optional[str] = None

    if profile_img is not None:
        # 파일 유효성 검증
        S3Uploader.validate_file_name(profile_img)
        S3Uploader.validate_file_extension(profile_img)
        content_type = getattr(profile_img, "content_type", None)
        S3Uploader.validate_file_content_type(content_type)
        ext = str(profile_img.name).rsplit(".", 1)[-1].lower()
        S3Uploader.validate_file_mime(ext, content_type)

        prefix = f"profiles/"
        profile_img.name = f"{user.uuid}_{profile_img.name}"  # 파일명 앞에 uuid 붙여서 구분

        new_profile_url = S3Uploader.upload_file(profile_img, prefix=prefix)
        uploaded_new_key = _extract_key_from_url(new_profile_url)

        # 기존 이미지 키(삭제 후보)
        old_key_to_delete = _extract_key_from_url(user.profile_img_url) if new_profile_url else None

    try:
        with transaction.atomic():
            update_fields: list[str] = []

            if nickname is not None:
                user.nickname = nickname
                update_fields.append("nickname")
            if new_profile_url is not None:
                user.profile_img_url = new_profile_url
                update_fields.append("profile_img_url")
            if phone_number is not None:
                user.phone_number = phone_number
                update_fields.append("phone_number")
            # 변경된 필드만 저장
            if update_fields:
                user.save(update_fields=update_fields)
    except Exception:
        # DB 저장 실패시 새로 올린 이미지 보상 삭제
        if uploaded_new_key:
            try:
                S3Uploader.delete_file(uploaded_new_key)
            except Exception:
                logger.exception("보상 삭제 실패(신규 프로필 이미지)")
        raise

    # 커밋 성공 후 기존 이미지 삭제
    if old_key_to_delete:
        try:
            S3Uploader.delete_file(old_key_to_delete)
        except Exception:
            logger.exception("기존 프로필 이미지 삭제 실패")

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
