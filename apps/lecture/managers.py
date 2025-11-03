from typing import TYPE_CHECKING, Self

from django.db.models import Q, QuerySet

from apps.users.models import User

if TYPE_CHECKING:
    from apps.lecture.models import LectureBookmark


class LectureBookmarkQuerySet(QuerySet["LectureBookmark"]):
    """LectureBookmark QuerySet"""

    def for_user(self, user: "User") -> Self:
        """특정 사용자의 북마크만 조회"""
        return self.filter(user=user).select_related("lecture").order_by("-created_at")

    def search(self, search_term: str) -> Self:
        """강의명 또는 강사명으로 검색"""
        if not search_term:
            return self
        return self.filter(Q(lecture__title__icontains=search_term) | Q(lecture__instructor__icontains=search_term))
