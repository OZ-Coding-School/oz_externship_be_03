from typing import Any

from django.db import models
from django_filters import (
    rest_framework as filters,  # type: ignore #mypy에서 django_filter 라이브러리 인식 불가능
)

from apps.lecture.models import CrawledLecture


class LectureFilter(filters.FilterSet):  # type: ignore #mypy에서 django_filter 라이브러리 인식 불가능
    """강의 목록 필터링"""

    # 검색 기능
    search = filters.CharFilter(method="filter_search", label="검색어 (강의명, 강사명)")

    # 카테고리 필터링
    category = filters.NumberFilter(field_name="lecture_categories__category__id", label="카테고리 ID")

    # 정렬 기능
    ordering = filters.OrderingFilter(
        fields=(
            ("created_at", "created_at"),  # 최신순
            ("original_price", "price"),  # 가격순
            ("average_rating", "rating"),  # 평점순
        ),
        field_labels={
            "created_at": "최신순",
            "price": "가격",
            "rating": "평점",
        },
    )

    class Meta:
        model = CrawledLecture
        fields = ["category"]

    def filter_search(self, queryset: Any, name: str, value: str) -> Any:
        """강의명 또는 강사명으로 검색"""
        if not value:
            return queryset

        return queryset.filter(models.Q(title__icontains=value) | models.Q(instructor__icontains=value)).distinct()
