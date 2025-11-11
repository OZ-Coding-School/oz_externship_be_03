from django.urls import path

from apps.notifications.views.read_views import (
    mark_all_notification_as_read,
    mark_notification_as_read,
)
from apps.notifications.views.views import NotificationListAPIView

urlpatterns = [
    path("notifications/<int:notification_id>/read/", mark_notification_as_read, name="notification-read"),
    path("notifications/read-all/", mark_all_notification_as_read, name="notification-read-all"),
    path("", NotificationListAPIView.as_view(), name="notification-list"),
]
