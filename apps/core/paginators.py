from typing import Any

from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response


class StandardPageNumberPagination(PageNumberPagination):
    """
    쿼리파라미터: ?page=1&limit=20
    """

    page_size = 20
    page_size_query_param = "limit"
    max_page_size = 500

    def meta(self, request: Request) -> dict[str, Any]:
        page_obj = getattr(self, "page", None)
        if not page_obj:
            size = self.get_page_size(request) or self.page_size
            return {"page": 1, "limit": size, "total": 0, "pages": 0, "next": None, "previous": None}

        return {
            "page": page_obj.number,
            "limit": self.get_page_size(request) or self.page_size,
            "total": page_obj.paginator.count,
            "pages": page_obj.paginator.num_pages,
            "next": self.get_next_link(),
            "previous": self.get_previous_link(),
        }
