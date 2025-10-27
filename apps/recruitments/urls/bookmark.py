from django.urls import path

from apps.recruitments.views.bookmark import (
    BookmarkListCreateAPIView,
    BookmarkRetrieveDestroyAPIView,
)

urlpatterns = [
    path("", BookmarkListCreateAPIView.as_view(), name="recruitments-bookmark-list-create"),
    # uuid 기준으로 상세 조회/삭제
    path(
        "<uuid:bookmark_uuid>/", BookmarkRetrieveDestroyAPIView.as_view(), name="recruitments-bookmark-detail-destroy"
    ),
]
