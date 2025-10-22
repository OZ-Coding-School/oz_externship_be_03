from asgiref.sync import sync_to_async
from django_redis import get_redis_connection
from apps.notifications.models import Notification
from django.core.cache import cache
from datetime import timedelta
from django.utils import timezone

async def get_user_notifications(user_id:int):
    '''Redis에서 새 알림 확인 -> DB에서 상세 정보 가져오기(비동기)'''
    #Redis에서 새 알림 ID 목록 가져오기
    redis_client = get_redis_connection('default')

    # Redis에서 실시간 알림 ID들 가져오고 삭제
    notification_ids = []
    while True:
        notification_id = redis_client.lpop(f"notifications:{user_id}")
        if not notification_id:
            break
        notification_ids.append(int(notification_id))
    # 마지막 처리 시간 가져오기 (중복 방지용)
    last_processed_key = f"last_notification_time: {user_id}"
    last_processed_time = await sync_to_async(cache.get)(last_processed_key,timezone.now() - timedelta(minutes=1))


    # DB에서 새로운 알림들만 필터링해서 가져오기
    new_notifications = await sync_to_async(
        lambda:list(Notification.objects.filter(
            user_id=user_id,
            created_at__gt=last_processed_time
        ).order_by('-created_at'))
    )()

    # 마지막 처리 시간 업데이트
    if new_notifications:
        await sync_to_async(cache.set)(last_processed_key, timezone.now(), timeout=86400)

    return new_notifications

