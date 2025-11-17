import asyncio
import logging
from datetime import date, timedelta

from celery import shared_task  # type: ignore
from django.conf import settings

from apps.notifications.models import Notification
from apps.notifications.services.redis_pubsub_classify import notification_pubsub
from apps.studies.models.schedules import ScheduleParticipant

logger = logging.getLogger(__name__)


@shared_task(async_=True)  # type: ignore[misc]
def send_to_pubsub(notification_id: int) -> None:
    async def _async_task() -> None:
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

    try:
        event_loop = asyncio.get_event_loop()
    except RuntimeError:
        event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(event_loop)

    if event_loop.is_running():
        asyncio.create_task(_async_task())
    else:
        event_loop.run_until_complete(_async_task())


@shared_task  # type: ignore[misc]
def send_study_group_notification(notification_id: int, study_group_id: str) -> None:
    async def _async_task() -> None:
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

    try:
        event_loop = asyncio.get_event_loop()
    except RuntimeError:
        event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(event_loop)

    if event_loop.is_running():
        asyncio.create_task(_async_task())
    else:
        event_loop.run_until_complete(_async_task())


@shared_task(name="send_tomorrow_schedule_notifications")  # type: ignore[misc]
def send_tomorrow_schedule_notifications() -> None:
    """예정 스케줄 알림 생성 및 배치 작업"""
    try:
        tomorrow = date.today() + timedelta(days=1)

        participants = ScheduleParticipant.objects.filter(schedule__session_date=tomorrow).select_related(
            "schedule", "schedule__study_group", "member__user"  # ScheduleParticipant -> schedule -> study_group
        )

        notifications = [
            Notification(
                user_id=participant.member.user.id,
                content=f"내일은 {participant.schedule.study_group.name}에서 "
                f"{participant.schedule.title}이 예정되어 있습니다! 잊지말고 참여해주세요!",
                type=Notification.NotificationType.STUDY_SCHEDULE_UPCOMING,
                back_url_link=f"https://study.ozcoding.site/study-groups/{participant.schedule.study_group.uuid}",
            )
            for participant in participants
        ]

        created_notifications = Notification.objects.bulk_create(notifications)

        for notification in created_notifications:
            send_to_pubsub.delay(notification.id)

    except Exception as e:
        logger.error(f"예정 스케줄 알림 태스크 오류: {e}")


@shared_task(name="send_today_schedule_notifications")  # type: ignore[misc]
def send_today_schedule_notifications() -> None:
    """당일 스케줄 알림 생성 및 배치 작업"""
    try:
        today = date.today()

        participants = ScheduleParticipant.objects.filter(schedule__session_date=today).select_related(
            "schedule", "schedule__study_group", "member__user"  # ScheduleParticipant -> schedule -> study_group
        )

        notifications = [
            Notification(
                user_id=participant.member.user.id,
                content=f"금일 {participant.schedule.start_time.strftime('%H:%M')}부터 "
                f"{participant.schedule.end_time.strftime('%H:%M')}까지 "
                f"{participant.schedule.study_group.name}에서 {participant.schedule.title}이 "
                f"예정되어 있습니다! 잊지말고 참여해주세요!",
                type=Notification.NotificationType.STUDY_SCHEDULE_TODAY,
                back_url_link=f"https://study.ozcoding.site/study-groups/{participant.schedule.study_group.uuid}",
            )
            for participant in participants
        ]

        created_notifications = Notification.objects.bulk_create(notifications)

        for notification in created_notifications:
            send_to_pubsub.delay(notification.id)

    except Exception as e:
        logger.error(f"금일 스케줄 알림 태스크 오류: {e}")
