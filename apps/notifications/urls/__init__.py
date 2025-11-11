from django.urls import URLPattern, URLResolver

from apps.notifications.urls.api_urls import urlpatterns as api_urlpatterns
from apps.notifications.urls.sse_urls import urlpatterns as sse_urlpatterns

app_name = "notifications"

urlpatterns: list[URLPattern | URLResolver] = [
    *sse_urlpatterns,
    *api_urlpatterns,
]
