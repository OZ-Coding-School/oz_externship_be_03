import logging
from datetime import datetime

from celery import shared_task  # type: ignore[import-untyped]
from django.utils import timezone

from apps.studies.models.groups import StudyGroup


@shared_task  # type: ignore[misc]
def update_studygroup_status_daily() -> None:
    """스터디 종료일이 지난 그룹의 상태를 ENDED로 자동 업데이트"""
    today = timezone.localdate()

    # 오늘 0시 0분의 timezone-aware datetime 만들기
    midnight = timezone.make_aware(datetime.combine(today, datetime.min.time()))

    ended = StudyGroup.objects.filter(end_at__lt=midnight, status="ONGOING")
    count = ended.update(status="ENDED")
    logger = logging.getLogger(__name__)

    logger.info(f"[Scheduler] {count} study groups marked as ENDED.")
