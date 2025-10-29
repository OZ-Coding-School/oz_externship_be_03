from django.urls import path

from apps.recruitments.views.tag import TagListCreateView

urlpatterns = [
    path("tags", TagListCreateView.as_view(), name="tag-list"),
]
