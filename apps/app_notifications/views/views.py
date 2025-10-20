from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.request import Request

from apps.app_notifications.models import Notification
from apps.app_notifications.serializers.notifications_serializers import NotificationSerializer

# (generics.py)
class NotificationListAPIView(generics.ListAPIView):
    # 어떤 serializer로 결과를 직렬화할지 지정 (notifications_serializers.py)
    serializer_class = NotificationSerializer
    # 인증된 사용자만 접근 가능하게 설정 (permissions.py)
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # 요청을 보낸 사용자만의 알림을 조회하도록 쿼리셋을 반환
        user = self.request.user
        # 최신순으로 정렬 반환 타입은 Django QuerySet
        return Notification.objects.filter(user=user).order_by("-created_at")

    def list(self, request: Request, *args, **kwargs):

        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "count": queryset.count(),
            "results": serializer.data
        })
