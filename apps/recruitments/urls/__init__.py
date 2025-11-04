from django.urls import URLPattern, URLResolver, include, path

urlpatterns: list[URLPattern | URLResolver] = [
    path("bookmark/", include("apps.recruitments.urls.bookmark")),
    path("", include("apps.recruitments.urls.recruitments")),
]
