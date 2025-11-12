from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction
from django.db.models import Count, QuerySet

from apps.recruitments.models import Bookmark, Recruitment

if TYPE_CHECKING:
    from apps.users.models import User


@transaction.atomic
def toggle_bookmark(recruitment: Recruitment, user: User) -> bool:
    """북마크 토글 기능"""
    bookmark, created = Bookmark.objects.get_or_create(
        recruitment=recruitment,
        user=user,
    )
    if not created:
        bookmark.delete()
        return False
    return True


def get_bookmarked_recruitments(user: User) -> QuerySet[Recruitment]:
    """특정 사용자가 북마크한 스터디 구인 공고 목록 조회"""
    return (
        Recruitment.objects.filter(bookmarks__user=user)
        .annotate(bookmark_count=Count("bookmarks"))
        .prefetch_related("tags", "images")
    )
