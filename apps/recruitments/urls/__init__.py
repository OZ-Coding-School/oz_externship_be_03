from django.urls import include, path

app_name = "recruitments"

urlpatterns = [
    path("", include("apps.recruitments.urls.recruitments")),
    path("/bookmarks", include("apps.recruitments.urls.bookmark")),
    path("/tags", include("apps.recruitments.urls.tag")),
    path("", include("apps.recruitments.urls.applications")),
]
