import logging

from celery import shared_task  # type: ignore

from apps.notifications.models import Notification
from apps.notifications.services.redis_pubsub_classify import notification_pubsub

logger = logging.getLogger(__name__)


@shared_task  # type: ignore[misc]
async def send_to_pubsub(notification_id: int) -> None:
    try:
        notification = await Notification.objects.select_related("user").aget(id=notification_id)

        await notification_pubsub.publish_notification(
            user_id=notification.user.id,
            notification_data={
                "id": notification.id,
                "type": notification.type,
                "content": notification.content,
                "back_url_link": notification.back_url_link,
                "created_at": notification.created_at.isoformat(),
                "is_read": notification.is_read,
            },
        )

    except Exception as e:
        logging.error(f"Redis pub 오류: {e}")


@shared_task  # type: ignore[misc]
async def send_study_group_notification(notification_id: int, study_group_id: str) -> None:
    try:
        notification = await Notification.objects.aget(id=notification_id)

        notification_data = {
            "id": notification.id,
            "type": notification.type,
            "content": notification.content,
            "back_url_link": notification.back_url_link,
            "created_at": notification.created_at.isoformat(),
            "is_read": notification.is_read,
        }

        await notification_pubsub.publish_group_notification(
            group_id=study_group_id, notification_data=notification_data
        )
    except Exception as e:
        logging.error(f"스터디 그룹 알림 발송 오류:{e}")
