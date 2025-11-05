import os

from celery import Celery  # type: ignore[import-untyped]
from celery.schedules import crontab # type: ignore[import-untyped]

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")

app = Celery("config")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()  # 각 app의 tasks.py 자동 로드

app.conf.beat_schedule = {
    "crawl-inflearn-lectures-daily": {
        "task": "crawl_inflearn_lectures",
        "schedule": crontab(hour=0, minute=0),
    },
}