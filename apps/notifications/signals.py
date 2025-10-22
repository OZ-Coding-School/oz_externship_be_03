from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.lecture.models import Application
from apps.notifications.views.SSE_views import notification_stream


@receiver(post_save, sender=Application)
def notifications_created(sender, instance, created, **kwargs):
    if not created:
        return # 없으면 수정시에도 트리거가 발동됨

    recruitment = instance.recruitment
