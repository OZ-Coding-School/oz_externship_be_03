from django.urls import path

from apps.recruitments.views.tag import TagListView

urlpatterns = [
    path("recruitment-tags/", TagListView.as_view(), name="tag-list"),
]
