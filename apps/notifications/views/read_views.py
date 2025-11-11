from django.contrib.auth.models import AnonymousUser
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.notifications.models import Notification


# 개별 알림 읽음 처리
@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def mark_notification_as_read(request: Request, notification_id: int) -> Response:
    user = request.user
    assert not isinstance(user, AnonymousUser)  # mypy AnonymousUser 오류로 인해 타입 단언 추가

    try:
        notification = Notification.objects.get(id=notification_id, user=user)
    except Notification.DoesNotExist:
        return Response({"detail": "Notification not found"}, status=status.HTTP_404_NOT_FOUND)

    # 이미 읽음 상태인 경우, 추가 업데이트 없이 안내 메시지만 반환
    if notification.is_read:
        return Response({"detail": "Notification already read"}, status=status.HTTP_200_OK)

    notification.is_read = True
    notification.save(update_fields=["is_read"])

    return Response({"detail": "Notification marked as read"}, status=status.HTTP_200_OK)


# 전체 알림 읽음 처리
@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def mark_all_notification_as_read(request: Request) -> Response:
    user = request.user
    assert not isinstance(user, AnonymousUser)  # mypy AnonymousUser 오류로 인해 타입 단언 추가

    # 해당 사용자의 읽지 않은(is_read=False) 알림을 모두 읽음(True)으로 변경
    updated_count = Notification.objects.filter(user=user, is_read=False).update(is_read=True)
    return Response({"detail": f"{updated_count} notifications marked as read."}, status=status.HTTP_200_OK)
