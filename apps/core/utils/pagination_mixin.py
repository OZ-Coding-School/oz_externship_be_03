from typing import Any, Optional, Sequence, Union

from django.db.models.query import QuerySet
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response


class PaginationHandlerMixin:
    """페이지네이션 기능 믹스인 클래스."""

    pagination_class = PageNumberPagination
    _paginator: Optional[PageNumberPagination] = None

    @property
    def paginator(self) -> Optional[PageNumberPagination]:
        """paginator 인스턴스 반환."""
        if self._paginator is None:
            if self.pagination_class is None:
                self._paginator = None
            else:
                self._paginator = self.pagination_class()
        return self._paginator

    def paginate_queryset(self, queryset: Union[QuerySet[Any], Sequence[Any]]) -> Optional[Sequence[Any]]:
        """쿼리셋 혹은 리스트를 페이지 단위로 분할해 반환."""
        if self.paginator is None:
            return None
        return self.paginator.paginate_queryset(queryset, self.request, view=self)  # type: ignore[arg-type]

    def get_paginated_response(self, data: Any) -> Response:
        """페이지네이션된 데이터 포함한 Response 객체 반환."""
        assert self.paginator is not None
        return self.paginator.get_paginated_response(data)

    @property
    def request(self) -> Request:
        """현재 뷰에 바인딩된 Request 객체를 반환."""
        if not hasattr(self, "request") or self.request is None:
            raise AttributeError("Request has not been set on the view.")
        return self.request
