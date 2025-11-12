from __future__ import annotations

from typing import List

from django.db.models import QuerySet

from apps.recruitments.models import Recruitment, Tag


def search_tags(keyword: str) -> QuerySet[Tag]:
    qs = Tag.objects.all()
    if keyword:
        qs = qs.filter(name__icontains=keyword)
    return qs.order_by("name")[:20]


def add_tags_to_recruitment(recruitment: Recruitment, tag_names: List[str]) -> List[str]:
    """특정 공고에 태그 추가"""
    existing_count: int = recruitment.tags.count()
    if existing_count + len(tag_names) > 5:
        raise ValueError("공고당 최대 5개의 태그만 추가할 수 있습니다.")

    added_tags: List[str] = []

    for name in tag_names:
        name_clean = name.strip()
        tag, _ = Tag.objects.get_or_create(name=name_clean)

        # 중복 방지
        if recruitment.tags.filter(pk=tag.pk).exists():
            raise ValueError(f"이미 등록된 태그입니다: {tag.name}")

        recruitment.tags.add(tag)
        added_tags.append(tag.name)

    return added_tags
