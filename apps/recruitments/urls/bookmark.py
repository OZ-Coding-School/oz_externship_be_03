from django.urls import path

from apps.recruitments.views.bookmark import (
    BookmarkListCreateAPIView,
    BookmarkRetrieveDestroyAPIView,
)

urlpatterns = [
    path("", BookmarkListCreateAPIView.as_view(), name="bookmark-list-create"),
    path(
        "<uuid:bookmark_uuid>/",
        BookmarkRetrieveDestroyAPIView.as_view(),
        name="bookmark-detail-destroy",
    ),
]
