from typing import Any, Optional

from django.core.paginator import Page, Paginator
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.utils.urls import remove_query_param, replace_query_param

from apps.chat.models import ChatMessage


class ChatMessagePagination(PageNumberPagination):
    page_size: Optional[int] = 100  # 기본 페이지 크기
    request: Request
    page: Page[ChatMessage]

    def get_page_size(self, request: Request) -> int:
        self.page_size = super().get_page_size(request)
        # 첫 페이지인 경우 300개의 메시지를 반환
        if request.query_params.get(self.page_query_param, "1") == "1":
            self.page_size = 300
        else:
            self.page_size = 100

        return self.page_size

    def get_page_number(self, request: Request, paginator: Paginator) -> int:  # type: ignore[type-arg]
        page_number = int(super().get_page_number(request, paginator))
        if page_number >= 2:
            page_number = page_number + 2
        return page_number

    def get_next_link(self) -> Optional[str]:
        if not self.page.has_next():
            return None
        url = self.request.build_absolute_uri()
        page_number = self.page.next_page_number()
        if int(page_number) >= 5:
            page_number = page_number - 2
        return replace_query_param(url, self.page_query_param, page_number)

    def get_previous_link(self) -> Optional[str]:
        if not self.page.has_previous():
            return None
        url = self.request.build_absolute_uri()
        page_number = self.page.previous_page_number()
        if int(page_number) >= 3:
            page_number = page_number - 2
        return replace_query_param(url, self.page_query_param, page_number)
