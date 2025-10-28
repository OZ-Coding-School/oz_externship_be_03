# mypy: ignore-errors
from datetime import datetime, timedelta
from typing import Any

from django.utils import timezone
from django_celery_beat.models import PeriodicTask  # type: ignore[import-untyped]
from freezegun import freeze_time

from apps.studies.models.groups import StudyGroup
from apps.studies.tasks import update_studygroup_status_daily


def test_update_studygroup_status_daily_marks_ended(db: Any) -> None:
    yesterday = timezone.localdate() - timedelta(days=1)
    today = timezone.localdate()

    ended_group = StudyGroup.objects.create(
        name="어제끝난그룹",
        start_at=yesterday - timedelta(days=3),
        end_at=yesterday,
        status="ONGOING",
        leader_id=1,  # type: ignore[attr-defined]
        max_members=5,  # type: ignore[attr-defined]
    )

    ongoing_group = StudyGroup.objects.create(
        name="오늘까지진행",
        start_at=today - timedelta(days=3),
        end_at=today,
        status="ONGOING",
        leader_id=1,  # type: ignore[attr-defined]
        max_members=5,  # type: ignore[attr-defined]
    )

    with freeze_time(datetime.combine(today, datetime.min.time()) + timedelta(minutes=1)):
        update_studygroup_status_daily()

    ended_group.refresh_from_db()
    ongoing_group.refresh_from_db()

    assert ended_group.status == "ENDED"
    assert ongoing_group.status == "ONGOING"


def test_scheduler_registration_on_startup(db: Any) -> None:
    from apps.core.apps import CoreConfig

    config = CoreConfig("apps.core", None)
    config.ready()

    task = PeriodicTask.objects.filter(name="update-studygroup-status-daily").first()
    assert task is not None
    assert task.task == "apps.studies.tasks.update_studygroup_status_daily"
