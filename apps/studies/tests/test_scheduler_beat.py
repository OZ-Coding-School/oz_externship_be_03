from django.test import TestCase
from django_celery_beat.models import (  # type: ignore[import-untyped]
    CrontabSchedule,
    PeriodicTask,
)


class CeleryBeatSchedulerTest(TestCase):
    def test_update_studygroup_task_registered_in_db_scheduler(self) -> None:
        """REQ-STDY-010: 스터디 그룹 상태 자동 업데이트 작업이 DB 기반 스케줄러에 등록되는지 확인"""
        crontab, _ = CrontabSchedule.objects.get_or_create(minute=1, hour=0)
        task, created = PeriodicTask.objects.get_or_create(
            crontab=crontab,
            name="update-studygroup-status-daily",
            task="apps.studies.tasks.update_studygroup_status_daily",
            enabled=True,
        )
        self.assertTrue(task.enabled)
        self.assertEqual(task.task, "apps.studies.tasks.update_studygroup_status_daily")
