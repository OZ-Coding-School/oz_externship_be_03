from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"

    def ready(self) -> None:
        # 스터디 그룹 상태 업데이트
        from apps.core.scheduler import register_periodic_task

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
