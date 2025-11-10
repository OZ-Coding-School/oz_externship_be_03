from django.urls import path
from apps.notifications.views.read_views import (mark_notification_as_read, mark_all_notification_as_read)

urlpatterns = [
    path("notifications/<int:notification_id>/read/", mark_notification_as_read, name="notification-read"),
    path("notifications/read-all/", mark_all_notification_as_read, name="notification-read-all"),
]