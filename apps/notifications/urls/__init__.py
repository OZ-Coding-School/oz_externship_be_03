from django.urls import URLPattern, URLResolver

from apps.notifications.urls.list_urls import urlpatterns as list_urlpatterns
from apps.notifications.urls.sse_urls import urlpatterns as sse_urlpatterns
from apps.notifications.urls.read_urls import urlpatterns as read_urlpatterns

app_name = "notifications"

urlpatterns: list[URLPattern | URLResolver] = [
    *list_urlpatterns,
    *sse_urlpatterns,
    *read_urlpatterns,
]
