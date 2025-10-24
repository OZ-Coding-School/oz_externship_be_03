from django.urls import path

from apps.recruitments.views.tag import TagListAPIView

urlpatterns = [
    path("tags/", TagListAPIView.as_view(), name="tag-list"),
]
