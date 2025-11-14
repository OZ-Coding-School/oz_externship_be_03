from typing import Any

from django.contrib.auth.models import AnonymousUser
from django.db.models import Count, Q, QuerySet
from rest_framework import generics, permissions
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.request import Request
from rest_framework.response import Response

from apps.notifications.models import Notification
from apps.notifications.serializers.notifications_serializers import (
    NotificationSerializer,
)


class NotificationListAPIView(generics.ListAPIView[Notification]):
    # 어떤 serializer로 결과를 직렬화할지 지정 (notifications_serializers.py)
    serializer_class = NotificationSerializer
    # 인증된 사용자만 접근 가능하게 설정 (permissions.py)
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = LimitOffsetPagination

    def get_queryset(self) -> QuerySet[Notification]:
        # 요청을 보낸 사용자만의 알림을 조회하도록 쿼리셋을 반환
        user = self.request.user
        if isinstance(user, AnonymousUser):
            return Notification.objects.none()
        # 최신순으로 정렬 반환 타입은 Django QuerySet
        return Notification.objects.filter(user=user).order_by("-created_at")

    def get_paginator(self) -> LimitOffsetPagination:
        paginator = self.pagination_class()
        paginator.default_limit = 10
        paginator.max_limit = 100
        return paginator

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        # 알림 목록을 count + results 형태로 반환 (페이지네이션 적용)
        queryset = self.get_queryset()

        # 페이지네이션 적용
        paginator = self.get_paginator()
        page = paginator.paginate_queryset(queryset, request)
        serializer = self.get_serializer(page, many=True)

        # counts는 전체 queryset에서 계산
        counts = queryset.aggregate(
            total=Count("id"), unread=Count("id", filter=Q(is_read=False)), read=Count("id", filter=Q(is_read=True))
        )

        # 페이지네이션 응답에 counts 추가
        response = paginator.get_paginated_response(serializer.data)
        response.data["counts"] = counts
        return response
