import logging

from asgiref.sync import async_to_sync
from celery import shared_task

from apps.notifications.models import Notification
from apps.notifications.services.redis_pubsub_classify import notification_pubsub
from apps.recruitments.models import Recruitment
from config import settings

logger = logging.getLogger(__name__)


@shared_task
def send_to_pubsub(notification_id: int) -> None:
    try:
        notification = Notification.objects.select_related("user").get(id=notification_id)

        async_to_sync(notification_pubsub.publish_notification)(
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
