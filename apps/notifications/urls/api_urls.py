from django.urls import path

from apps.notifications.views.read_views import (
    NotificationReadAllAPIView,
    NotificationReadAPIView,
)
from apps.notifications.views.views import NotificationListAPIView

urlpatterns = [
    path("", NotificationListAPIView.as_view(), name="notification-list"),
    path("/<int:notification_id>/read", NotificationReadAPIView.as_view(), name="notification-read"),
    path("/read-all", NotificationReadAllAPIView.as_view(), name="notification-read-all"),
]
