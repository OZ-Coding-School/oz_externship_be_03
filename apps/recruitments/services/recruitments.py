from __future__ import annotations

from typing import Any, Dict, List

from django.db import transaction
from django.db.models import Count, QuerySet

from apps.core.utils.s3_uploader import S3Uploader  # S3Uploader 클래스 기준
from apps.recruitments.models import Recruitment, RecruitmentAttachment, Tag
from apps.users.models import User


@transaction.atomic
def create_recruitment(author: User, validated_data: dict[str, Any]) -> Recruitment:
    tag_names: list[str] = validated_data.pop("tags", [])
    attachments_data: list[dict[str, Any]] = validated_data.pop("attachments", [])
    estimated_fee: int = validated_data.get("estimated_fee") or _calculate_estimated_fee(validated_data)
    validated_data["estimated_fee"] = estimated_fee

    recruitment: Recruitment = Recruitment.objects.create(author=author, **validated_data)
    _set_recruitment_tags(recruitment, tag_names)
    _create_attachments(recruitment, attachments_data)
    return recruitment


@transaction.atomic
def update_recruitment(recruitment: Recruitment, validated_data: dict[str, Any]) -> Recruitment:
    tag_names: list[str] | None = validated_data.pop("tags", None)
    attachments_data: list[dict[str, Any]] | None = validated_data.pop("attachments", None)
    estimated_fee: int = validated_data.get("estimated_fee") or _calculate_estimated_fee(validated_data)
    validated_data["estimated_fee"] = estimated_fee

    for attr, value in validated_data.items():
        setattr(recruitment, attr, value)
    recruitment.save()

    if tag_names is not None:
        _set_recruitment_tags(recruitment, tag_names)
    if attachments_data is not None:
        _create_attachments(recruitment, attachments_data)

    return recruitment


def _set_recruitment_tags(recruitment: Recruitment, tag_names: list[str]) -> None:
    recruitment.tags.clear()
    for name in tag_names[:5]:
        if name.strip():
            tag, _ = Tag.objects.get_or_create(name=name.strip())
            recruitment.tags.add(tag)


def _create_attachments(recruitment: Recruitment, attachments_data: list[dict[str, Any]]) -> None:
    recruitment.attachments.all().delete()  # 기존 attachment 삭제
    for attachment in attachments_data[:3]:
        file_name: str = str(attachment.get("file_name", ""))
        file_url: str = str(attachment.get("file_url", ""))
        RecruitmentAttachment.objects.create(
            recruitment=recruitment,
            file_name=file_name,
            file_url=file_url,
        )


def _calculate_estimated_fee(validated_data: dict[str, Any]) -> int:
    return 0  # 실제 계산 로직 구현 필요


def increase_views(recruitment: Recruitment) -> Recruitment:
    recruitment.views_count += 1
    recruitment.save(update_fields=["views_count"])
    return recruitment


def get_recommended_recruitments_for_user(user: User, limit: int = 3) -> QuerySet[Recruitment]:
    if not user.is_authenticated:
        return Recruitment.objects.none()
    return (
        Recruitment.objects.filter(is_closed=False)
        .annotate(bookmark_count=Count("bookmarks"))
        .order_by("-bookmark_count", "-views_count")[:limit]
    )


def generate_presigned_attachment_urls(files: list[dict[str, str]], prefix: str = "") -> list[dict[str, str]]:
    """
    S3 presigned-url 생성
    files: [{"file_name": str, "content_type": str}, ...]
    return: [{"file_name": str, "file_url": str}, ...]
    """
    # S3Uploader 클래스의 generate_presigned_urls 사용
    raw: list[dict[str, Any]] = S3Uploader.generate_presigned_urls(prefix, files)
    # 반환 타입을 명시적으로 str로 변환
    return [{"file_name": str(d["file_name"]), "file_url": str(d["file_url"])} for d in raw]
