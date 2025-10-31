from typing import Any, Optional

from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request


class ChatMessagePagination(PageNumberPagination):
    page_size = 100  # 기본 페이지 크기
    page_size_query_param = "page_size"
    max_page_size = 1000

    def paginate_queryset(self, queryset: Any, request: Request, view: Optional[Any] = None) -> Optional[list[Any]]:
        # 첫 페이지인 경우 300개의 메시지를 반환
        if request.query_params.get(self.page_query_param, "1") == "1":
            self.page_size = 300
        else:
            self.page_size = 100
        return super().paginate_queryset(queryset, request, view)
