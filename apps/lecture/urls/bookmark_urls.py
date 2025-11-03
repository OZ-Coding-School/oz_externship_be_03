from django.urls import path

from apps.lecture.views.bookmark_views import (
    LectureBookmarkDeleteView,
    LectureBookmarkListCreateView,
)

urlpatterns = [
    path("bookmarks", LectureBookmarkListCreateView.as_view(), name="bookmark-list-create"),
    path("bookmarks/<uuid:lecture_uuid>", LectureBookmarkDeleteView.as_view(), name="bookmark-delete"),
]
