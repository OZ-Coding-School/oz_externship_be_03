import asyncio
import logging
from typing import Any

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.notifications.models import Notification
from apps.notifications.services.redis_pubsub_classify import notification_pubsub
from apps.recruitments.models.application import Application

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Application)
def notifications_created(sender: Any, instance: Application, created: bool, **kwargs: Any) -> None:
    if not created:
        return  # 없으면 수정시에도 트리거가 발동됨

    recruitment = instance.recruitment

    notification = Notification.objects.create(
        user_id=recruitment.author_id,
        content=f"공고 '{recruitment.title}'에 새로운 지원자가 지원했습니다.",
        type=Notification.NotificationType.APPLICATION_CREATED,
        back_url_link=f"{settings.FRONTEND_DOMAIN}/studies/applications",
    )

    # Redis pub/sub으로 실시간 알림 발송
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(
                notification_pubsub.publish_notification(
                    user_id=recruitment.author_id,
                    notification_data={
                        "id": notification.id,
                        "type": notification.type,
                        "content": notification.content,
                        "back_url_link": f"{settings.FRONTEND_DOMAIN}/studies/applications",
                        "created_at": notification.created_at.isoformat(),
                        "is_read": notification.is_read,
                    },
                )
            )
        else:
            asyncio.run(
                notification_pubsub.publish_notification(
                    user_id=recruitment.author_id,
                    notification_data={
                        "id": notification.id,
                        "type": notification.type,
                        "content": notification.content,
                        "back_url_link": f"{settings.FRONTEND_DOMAIN}/studies/applications",
                        "created_at": notification.created_at.isoformat(),
                        "is_read": notification.is_read,
                    },
                )
            )
    except Exception as e:
        logger.error(f"Redis pub 오류:{e}")
