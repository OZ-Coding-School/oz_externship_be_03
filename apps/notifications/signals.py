import logging
from typing import Any

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.notifications.models import Notification
from apps.notifications.tasks import send_study_group_notification, send_to_pubsub
from apps.recruitments.models.application import Application, ApplicationStatus

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Application)
def recruitment_apply_created(sender: Any, instance: Application, created: bool, **kwargs: Any) -> None:
    """공고 지원시 알림 생성"""
    if not created:
        return  # 없으면 수정시에도 트리거가 발동됨

    recruitment = instance.recruitment

    notification = Notification.objects.create(
        user_id=recruitment.author_id,
        content=f"공고 '{recruitment.title}'에 새로운 지원자가 지원했습니다.",
        type=Notification.NotificationType.APPLICATION_CREATED,
        back_url_link=f"{settings.FRONTEND_DOMAIN}/api/admin/recruitments",
    )

    send_to_pubsub.delay(notification.id)


@receiver(post_save, sender=Application)
def application_approved_rejected_created(sender: Any, instance: Application, created: bool, **kwargs: Any) -> None:
    """공고 지원 승인/거절 알림"""
    if not created and instance.status in [ApplicationStatus.APPROVED, ApplicationStatus.REJECTED]:
        recruitment = instance.recruitment

        if instance.status == ApplicationStatus.APPROVED:
            notification = Notification.objects.create(
                user_id=instance.user_id,
                content=f"'{recruitment.title}' 구인 공고에 대한 지원내역이 승인되었습니다.",
                type=Notification.NotificationType.APPLICATION_STATUS_APPROVAL,
                back_url_link=f"{settings.FRONTEND_DOMAIN}/api/v1/applications",
            )
        else:
            notification = Notification.objects.create(
                user_id=instance.user_id,
                content=f"'{recruitment.title}' 구인 공고에 대한 지원내역이 거절되었습니다.",
                type=Notification.NotificationType.APPLICATION_STATUS_REJECTION,
                back_url_link=f"{settings.FRONTEND_DOMAIN}/api/v1/applications",
            )

        send_to_pubsub.delay(notification.id)


@receiver(post_save, sender=Application)
def study_member_joined_created(sender: Any, instance: Application, created: bool, **kwargs: Any) -> None:
    """스터디 그룹 새 멤버 참여 알림"""
    if not created and instance.status == ApplicationStatus.APPROVED:
        recruitment = instance.recruitment

        if recruitment.study_group:
            study_group = recruitment.study_group
            new_member = instance.user

            notification = Notification.objects.create(
                user_id=new_member.id,
                content=f"{study_group.name}에 {new_member.nickname}님이 참여했습니다. 환영해주세요!",
                type=Notification.NotificationType.STUDY_MEMBER_JOINED,
                back_url_link=f"{settings.FRONTEND_DOMAIN}api/v1/chat/ws/study-groups/{study_group.id}",
            )

            send_study_group_notification.delay(notification.id, study_group.id)
