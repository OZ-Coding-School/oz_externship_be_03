from django.urls import URLPattern, URLResolver

from apps.notifications.urls.list_urls import urlpatterns as list_urlpatterns
from apps.notifications.urls.sse_urls import urlpatterns as sse_urlpatterns

app_name = "notifications"

urlpatterns: list[URLPattern | URLResolver] = [
    *sse_urlpatterns,
    *list_urlpatterns,
]
