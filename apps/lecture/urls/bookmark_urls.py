from django.urls import path

from apps.lecture.views.bookmark_views import (
    LectureBookmarkButtonAPIView,
    LectureBookmarkListAPIView,
)

urlpatterns = [
    path("/<int:lecture_id>/bookmarks", LectureBookmarkButtonAPIView.as_view(), name="bookmark-button"),
    path("/me/bookmarks", LectureBookmarkListAPIView.as_view(), name="bookmark-list"),
]
