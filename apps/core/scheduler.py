import json
import logging
from typing import Any

from django.db.utils import OperationalError, ProgrammingError
from django_celery_beat.models import (  # type: ignore[import-untyped]
    CrontabSchedule,
    PeriodicTask,
)

logger = logging.getLogger(__name__)


def register_periodic_task(
    name: str, task_path: str, hour: str, minute: str = "0", day_of_week: str = "*", **kwargs: Any
) -> None:
    try:
        schedule, _ = CrontabSchedule.objects.get_or_create(
            hour=hour,
            minute=minute,
            day_of_week=day_of_week,
        )
        PeriodicTask.objects.update_or_create(
            name=name,
            defaults={
                "crontab": schedule,
                "task": task_path,
                "one_off": False,
                "enabled": True,
                "kwargs": json.dumps(kwargs),
            },
        )
        logger.info(f"[Scheduler] Registered periodic task: {name}")
    except (OperationalError, ProgrammingError):
        pass
