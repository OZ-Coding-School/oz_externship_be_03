import os

from celery import Celery
from celery.app.task import Task

# Set the default django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

app = Celery("config")

# namespace = 접두사 역할(모든 설정에 CELERY가 붙어야 작동한다.)
# CELERY_BROKEN_URL -> broken_url
app.config_from_object("django.conf:settings", namespace="CELERY")
# tasks.py를 스캔
app.autodiscover_tasks()

# mypy: disable-error-code=misc
@app.task(bind=True, ignore_result=True)
def debug_task(self: Task) -> None:
    print(f"Request: {self.request!r}")
