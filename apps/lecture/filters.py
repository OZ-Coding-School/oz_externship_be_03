from typing import Any

from django.db.models import Q
from django_filters import rest_framework as filters  # type: ignore

from apps.lecture.models import CrawledLecture


class LectureFilter(filters.FilterSet):  # type: ignore
    # mypy에서 django_filter 라이브러리 인식 불가능
    """강의 목록 필터링"""

    # 검색 기능
    search = filters.CharFilter(method="filter_search", label="검색어")

    # 카테고리 필터링
    category = filters.CharFilter(field_name="lecture_categories__category__name", label="카테고리명")

    # 플랫폼 필터링
    platform = filters.ChoiceFilter(
        choices=[("UDEMY", "Udemy"), ("INFLEARN", "Inflearn")], method="filter_platform", label="플랫폼"
    )

    # 정렬 기능
    ordering = filters.OrderingFilter(
        fields=(
            ("created_at", "created_at"),  # 시간순
            ("original_price", "price"),  # 가격순
            ("average_rating", "rating"),  # 평점순
        ),
        field_labels={
            "created_at": "시간순",
            "price": "가격순",
            "rating": "평점순",
        },
    )

    class Meta:
        model = CrawledLecture
        fields = ["category"]

    def filter_search(self, queryset: Any, name: str, value: str) -> Any:
        """강의명 또는 강사명으로 검색"""
        if not value:
            return queryset

        search_type = self.request.query_params.get("search_type", "all")

        if search_type == "title":
            return queryset.filter(title__icontains=value)
        elif search_type == "instructor":
            return queryset.filter(instructor__icontains=value)
        else:
            return queryset.filter(Q(title__icontains=value) | Q(instructor__icontains=value)).distinct()

    def filter_platform(self, queryset: Any, name: str, value: str) -> Any:
        """플랫폼 필터"""
        if not value:
            return queryset
        return queryset.filter(platform=value.upper())
