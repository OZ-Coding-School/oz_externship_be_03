from __future__ import annotations

from typing import Any

from django.db import transaction
from django.db.models import Count, QuerySet

from apps.recruitments.models import Recruitment, Tag
from apps.users.models import User


@transaction.atomic
def create_recruitment(author: User, validated_data: dict[str, Any]) -> Recruitment:
    tag_names = validated_data.pop("tags", [])
    recruitment: Recruitment = Recruitment.objects.create(author=author, **validated_data)
    _set_recruitment_tags(recruitment, tag_names)
    return recruitment


@transaction.atomic
def update_recruitment(recruitment: Recruitment, validated_data: dict[str, Any]) -> Recruitment:
    tag_names = validated_data.pop("tags", None)
    for attr, value in validated_data.items():
        setattr(recruitment, attr, value)
    recruitment.save()
    if tag_names is not None:
        _set_recruitment_tags(recruitment, tag_names)
    return recruitment


def _set_recruitment_tags(recruitment: Recruitment, tag_names: list[str]) -> None:
    recruitment.tags.clear()
    for name in tag_names[:5]:
        tag, _ = Tag.objects.get_or_create(name=name.strip())
        recruitment.tags.add(tag)


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
