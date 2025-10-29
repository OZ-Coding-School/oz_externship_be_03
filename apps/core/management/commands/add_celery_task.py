from typing import Any

from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask  # type: ignore[import-untyped]

from apps.core.scheduler import register_periodic_task


class Command(BaseCommand):
    def handle(self, *args: Any, **options: dict[str, Any]) -> None:
        try:
            register_periodic_task(
                name="update-studygroup-status-daily",
                task_path="apps.studies.tasks.update_studygroup_status_daily",
                hour="0",
                minute="1",
            )

            register_periodic_task(
                name="delete-withdrawn-users-daily",
                task_path="apps.users.tasks.delete_withdrawn_users",
                hour="0",
                minute="10",
                batch_size=1000,
            )

            scheduled_tasks = PeriodicTask.objects.all()
            for i, task in enumerate(scheduled_tasks):
                crontab = getattr(task, "crontab", None)
                scheduled_time = f"{crontab.hour}:{crontab.minute}" if crontab else "None"
                self.stdout.write(
                    f"Task {i}: {task.name}, scheduled_time: {scheduled_time}", style_func=self.style.SUCCESS
                )
            self.stdout.write("Celery tasks are registered successfully.", style_func=self.style.SUCCESS)
        except Exception as e:
            self.stderr.write(f"Error: {e}", style_func=self.style.ERROR)
