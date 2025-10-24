from django.urls import URLPattern,URLResolver,path
from apps.notifications.urls.sse_urls import (
    urlpatterns as sse_urlpatterns,
)

app_name = "notifications"

urlpatterns: list[URLPattern|URLResolver] = [
    *sse_urlpatterns,
]