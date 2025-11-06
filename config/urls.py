from django.conf import settings
from django.conf.urls.static import static
from django.urls import URLPattern, URLResolver, include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns: list[URLPattern | URLResolver] = [
    path("api/v1/lectures", include("apps.lecture.urls")),
    path("api/v1/admin/lectures", include("apps.lecture.urls.admin_urls")),
    path("api/v1/", include("apps.users.urls")),
    path("api/v1/", include("apps.recruitments.urls.tag")),
    path("api/v1/studies/", include("apps.studies.urls")),
    path("api/v1/recruitments/", include("apps.recruitments.urls")),
    path("api/v1/notifications/", include("apps.notifications.urls")),
    path("api/v1/applications/", include("apps.recruitments.urls.application")),
    path("api/v1/search-logs/", include("apps.recruitments.urls.search_log")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    if "debug_toolbar" in settings.INSTALLED_APPS:
        urlpatterns += [path("__debug__/", include("debug_toolbar.urls"))]
    if "drf_spectacular" in settings.INSTALLED_APPS:
        urlpatterns += [
            path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
            path("api/schema/swagger-ui/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
            path("api/schema/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
        ]
