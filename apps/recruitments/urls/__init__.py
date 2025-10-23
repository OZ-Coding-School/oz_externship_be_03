from django.urls import include, path

urlpatterns = [
    path("", include("apps.recruitments.urls.tag")),  # 태그 관련 Spec API URL 포함
]
