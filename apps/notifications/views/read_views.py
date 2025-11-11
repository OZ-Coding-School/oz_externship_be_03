from typing import Optional, cast

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notifications.models import Notification
from apps.notifications.permissions import IsNotificationOwner
from apps.users.models import User


# 개별 알림 읽음 처리
class NotificationReadAPIView(APIView):
    permission_classes = [IsAuthenticated, IsNotificationOwner]

    @extend_schema(
        tags=["Notifications"],
        summary="로그인 유저가 수신한 특정 알림을 읽음 처리하는 API입니다.",
        responses={
            200: {"type": "object", "example": {"detail": "ok"}},
            401: {"type": "object", "example": {"error": "자격 인증데이터가 제공되지 않았습니다."}},
            403: {
                "type": "object",
                "examples": {"error": "You do not have permission to perform this action."},
            },
            404: {"type": "object", "example": {"error": "not found"}},
        },
    )
    def post(self, request: Request, notification_id: int) -> Response:
        notification = self.get_object(notification_id)
        if not notification:
            return Response({"error": "not found"}, status=status.HTTP_404_NOT_FOUND)
        self.check_object_permissions(request, notification)
        notification.is_read = True
        notification.save(update_fields=["is_read"])

        return Response({"detail": "ok"}, status=status.HTTP_200_OK)

    def get_object(self, notification_id: int) -> Optional[Notification]:
        try:
            return Notification.objects.get(id=notification_id)
        except Notification.DoesNotExist:
            return None


# 전체 알림 읽음 처리
class NotificationReadAllAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Notifications"],
        summary="로그인 유저가 수신한 알림중 읽지않은 모든 알림을 읽음 처리하는 API입니다.",
        responses={
            200: {"type": "object", "example": {"detail": "ok"}},
            401: {"type": "object", "example": {"error": "자격 인증데이터가 제공되지 않았습니다."}},
        },
    )
    def post(self, request: Request) -> Response:
        user = cast(User, request.user)
        Notification.objects.filter(user=user, is_read=False).update(is_read=True)
        return Response({"detail": "ok"}, status=status.HTTP_200_OK)
