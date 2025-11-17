from __future__ import annotations

from typing import Any

from django.db import transaction
from django.db.models import Count, QuerySet

from apps.recruitments.models import Recruitment, Tag
from apps.users.models import User


@transaction.atomic
def create_recruitment(author: User, validated_data: dict[str, Any]) -> Recruitment:
    from apps.recruitments.models import RecruitmentAttachment

    tag_names = validated_data.pop("tags", [])
    attachments = validated_data.pop("attachments", [])

    validated_data.setdefault("estimated_fee", 0)

    recruitment: Recruitment = Recruitment.objects.create(author=author, **validated_data)
    _set_recruitment_tags(recruitment, tag_names)
    _set_recruitment_attachments(recruitment, attachments)
    return recruitment


@transaction.atomic
def update_recruitment(recruitment: Recruitment, validated_data: dict[str, Any]) -> Recruitment:
    tag_names = validated_data.pop("tags", None)
    attachments = validated_data.pop("attachments", None)
    for attr, value in validated_data.items():
        setattr(recruitment, attr, value)
    recruitment.save()
    if tag_names is not None:
        _set_recruitment_tags(recruitment, tag_names)
    if attachments is not None:
        _set_recruitment_attachments(recruitment, attachments)
    return recruitment


def _set_recruitment_tags(recruitment: Recruitment, tag_names: list[str]) -> None:
    recruitment.tags.clear()
    for name in tag_names[:5]:
        tag_name = name.strip()
        if tag_name and tag_name.lower() != "undefined":
            tag, _ = Tag.objects.get_or_create(name=tag_name)
            recruitment.tags.add(tag)


def _set_recruitment_attachments(recruitment: Recruitment, attachment_urls: list[str]) -> None:
    from apps.recruitments.models import RecruitmentAttachment

    # 기존 첨부파일 삭제
    recruitment.attachments.all().delete()

    # 새로운 첨부파일 추가 (최대 3개)
    for url in attachment_urls[:3]:
        if url and url.strip():
            # URL에서 파일명 추출
            file_name = url.split("/")[-1]
            RecruitmentAttachment.objects.create(recruitment=recruitment, file_url=url.strip(), file_name=file_name)


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
