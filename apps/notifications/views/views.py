from typing import Any

from django.contrib.auth.models import AnonymousUser
from django.db.models import QuerySet
from rest_framework import generics, permissions
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

    def get_queryset(self) -> QuerySet[Notification]:
        # 요청을 보낸 사용자만의 알림을 조회하도록 쿼리셋을 반환
        user = self.request.user
        if isinstance(user, AnonymousUser):
            return Notification.objects.none()
        # 최신순으로 정렬 반환 타입은 Django QuerySet
        return Notification.objects.filter(user=user).order_by("-created_at")

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:

        # 알림 목록을 count + results 형태로 반환
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({"count": queryset.count(), "results": serializer.data})
