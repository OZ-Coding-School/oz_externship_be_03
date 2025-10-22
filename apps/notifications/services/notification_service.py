from datetime import timedelta
from typing import List

from asgiref.sync import sync_to_async
from django.core.cache import cache
from django.utils import timezone
from django_redis import get_redis_connection  # type: ignore

from apps.notifications.models import Notification


async def get_user_notifications(user_id: int) -> List[Notification]:
    """Redis에서 새 알림 확인 -> DB에서 상세 정보 가져오기(비동기)"""
    # Redis에서 새 알림 ID 목록 가져오기
    redis_client = get_redis_connection("default")

    # Redis에서 실시간 알림 ID들 가져오고 삭제
    notification_ids = []
    while True:
        notification_id = redis_client.lpop(f"notifications:{user_id}")
        if not notification_id:
            break
        notification_ids.append(int(notification_id))

    #Redis에 신호가 있을 때만 DB 조회
    if not notification_ids:
        return [] # DB조회 생략

    #Redis ID로 DB에서 조회
    new_notifications = await sync_to_async(
        lambda: list(Notification.objects.filter(
            id__in=notification_ids,
            is_read=False
        ).order_by('-created_at'))
    )()

    return new_notifications
