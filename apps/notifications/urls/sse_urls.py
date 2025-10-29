from django.urls import path

from apps.notifications.views.SSE_views import notification_stream

app_name = "sse"

urlpatterns = [path("sse/<int:user_id>/", notification_stream, name="sse_stream")]
