from typing import TYPE_CHECKING, List, Self, Set

from django.db.models import Case, IntegerField, Prefetch, Q, QuerySet, Value, When

from apps.users.models import User

if TYPE_CHECKING:
    from apps.lecture.models.bookmark import LectureBookmark
    from apps.lecture.models.category import LectureCategory, UserPreferCategory
    from apps.lecture.models.lecture import CrawledLecture


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

    def lecture_ids_for_user(self, user_id: int) -> Set[int]:
        """사용자의 북마크 강의 ID 집합 반환"""
        return set(self.filter(user_id=user_id).values_list("lecture_id", flat=True))


class CrawledLectureQuerySet(QuerySet["CrawledLecture"]):
    """CrawledLecture QuerySet"""

    def with_categories(self) -> Self:
        """카테고리 정보 prefetch (N+1 방지)"""
        from apps.lecture.models.category import LectureCategory

        return self.prefetch_related(
            Prefetch("lecture_categories", queryset=LectureCategory.objects.select_related("category"))
        )

    def by_rating(self) -> Self:
        """평점 내림차순 정렬"""
        return self.order_by("-average_rating")

    def exclude_bookmarked(self, user_id: int) -> Self:
        """사용자가 북마크한 강의 제외"""
        from apps.lecture.models.bookmark import LectureBookmark

        bookmarked_ids = LectureBookmark.objects.lecture_ids_for_user(user_id)
        return self.exclude(id__in=bookmarked_ids)

    def ordered_by_ids(self, ordered_ids: List[int]) -> Self:
        """ID 순서대로 정렬 (추천 결과 순서 유지)"""
        return self.filter(id__in=ordered_ids).order_by(
            Case(*[When(id=id_, then=Value(i)) for i, id_ in enumerate(ordered_ids)], output_field=IntegerField())
        )

    def popular_lectures(self, top_n: int = 10) -> Self:
        """인기 강의 조회 (평점 순)"""
        return self.by_rating().with_categories()[:top_n]


class UserPreferCategoryQuerySet(QuerySet["UserPreferCategory"]):
    """UserPreferCategory QuerySet"""

    def for_user(self, user_id: int) -> Self:
        """특정 사용자의 선호 카테고리 조회"""
        return self.filter(user_id=user_id)

    def category_ids_for_user(self, user_id: int) -> Set[int]:
        """사용자의 선호 카테고리 ID 집합 반환"""
        return set(self.for_user(user_id).values_list("category_id", flat=True))
