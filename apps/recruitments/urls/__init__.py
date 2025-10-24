from django.urls import include, path

urlpatterns = [
    path("", include("apps.recruitments.urls.tag")),
]
