from django.urls import path

from apps.notifications.views.views import NotificationListAPIView

urlpatterns = [
    path("notifications/", NotificationListAPIView.as_view(), name="notification-list"),
]
