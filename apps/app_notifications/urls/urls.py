from django.urls import path
from apps.app_notifications.views.notifications_views import NotificationListAPIView

urlpatterns = [
    path("notifications/", NotificationListAPIView.as_view(), name="notification-list"),
]
