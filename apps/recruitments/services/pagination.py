from __future__ import annotations

from typing import Any, cast

from django.core.paginator import Page
from django.db.models import QuerySet
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class RecruitmentPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"

    def get_paginated_response(self, data: list[Any] | dict[str, Any]) -> Response:
        """커스텀 페이지네이션 응답 구조"""

        assert self.page is not None, "Pagination 'page' must not be None"
        assert self.request is not None, "Pagination 'request' must not be None"

        page: Page[Any] = self.page
        queryset: QuerySet[Any] = cast(QuerySet[Any], page.paginator.object_list)

        total: int = queryset.count()
        open_count: int = queryset.filter(is_closed=False).count()
        closed_count: int = total - open_count

        return Response(
            {
                "results": data,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "count": {
                    "total": total,
                    "open": open_count,
                    "closed": closed_count,
                },
            }
        )
