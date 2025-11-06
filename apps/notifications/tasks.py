import logging
from datetime import timedelta, date

from django.conf import settings
from celery import shared_task  # type: ignore

from apps.notifications.models import Notification
from apps.notifications.services.redis_pubsub_classify import notification_pubsub
from apps.studies.models import ScheduleParticipant

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

@shared_task(name="send_tomorrow_schedule_notifications") # type: ignore[misc]
def send_tomorrow_schedule_notifications() -> None:
    """예정 스케줄 알림 생성 및 배치 작업"""
    try:
        tomorrow = date.today() + timedelta(days=1)

        participants = ScheduleParticipant.objects.filter(
            schedule__session_date=tomorrow
        ).select_related(
            'schedule',
            'schedule__study_group', # ScheduleParticipant -> schedule -> study_group
            'member__user'
        )

        for participant in participants:
            schedule = participant.schedule
            study_group = participant.schedule.study_group
            user = participant.member.user

            notification = Notification.objects.create(
                user_id=user.id,
                content=f"내일은 {study_group.name}에서 {schedule.title}이 예정되어 있습니다! 잊지말고 참여해주세요!",
                type=Notification.NotificationType.STUDY_SCHEDULE_UPCOMING,
                back_url_link=f"{settings.FRONTEND_DOMAIN}/api/v1/studies/groups/{study_group.id}"
            )

            send_to_pubsub.delay(notification.id)

    except Exception as e:
        logger.error(f"예정 스케줄 알림 태스크 오류: {e}")



