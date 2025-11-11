from django.urls import path

from apps.notifications.views.SSE_views import notification_stream

urlpatterns = [path("/stream", notification_stream, name="notification_stream")]
