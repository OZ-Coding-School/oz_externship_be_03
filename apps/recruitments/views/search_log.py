from typing import Any

from django.contrib.auth.models import AnonymousUser
from django.db.models import QuerySet
from rest_framework.generics import ListAPIView, ListCreateAPIView
from rest_framework.serializers import BaseSerializer

from apps.recruitments.models.search_log import SearchLog
from apps.recruitments.serializers.search_log import SearchLogSerializer


class SearchLogListCreateAPIView(ListCreateAPIView[SearchLog]):
    queryset: QuerySet[SearchLog] = SearchLog.objects.all()
    serializer_class = SearchLogSerializer

    def perform_create(self, serializer: BaseSerializer[SearchLog]) -> None:
        ip = self.request.META.get("REMOTE_ADDR")
        user_agent = self.request.META.get("HTTP_USER_AGENT", "")
        user = self.request.user if not isinstance(self.request.user, AnonymousUser) else None
        serializer.save(user=user, ip=ip, user_agent=user_agent)


class RecentSearchLogAPIView(ListAPIView[SearchLog]):
    serializer_class = SearchLogSerializer

    def get_queryset(self) -> QuerySet[SearchLog]:
        user = self.request.user
        if isinstance(user, AnonymousUser):
            return SearchLog.objects.none()
        return SearchLog.objects.filter(user=user).order_by("-created_at")[:10]
