from typing import Any

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.notifications.events import notification_events
from apps.notifications.models import Notification
from apps.recruitments.models.application import Application


@receiver(post_save, sender=Application)
def notifications_created(sender: Any, instance: Application, created: bool, **kwargs: Any) -> None:
    if not created:
        return  # 없으면 수정시에도 트리거가 발동됨

    recruitment = instance.recruitment

    Notification.objects.create(
        user_id=recruitment.author_id,
        content=f"공고 '{recruitment.title}'에 새로운 지원자가 지원했습니다.",
        type="APPLICATION_CREATED",
        back_url_link=f"{settings.FRONTEND_DOMAIN}/studies/applications",
    )

    # 이벤트 시스템에 트리거 발송
    notification_events.notify_user(recruitment.author_id)
