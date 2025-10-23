from django.urls import path

from apps.recruitments.views.bookmark import (
    BookmarkListCreateAPIView,
    BookmarkRetrieveDestroyAPIView,
)

urlpatterns = [
    # 전체 조회 / 생성
    path("list/", BookmarkListCreateAPIView.as_view(), name="bookmark-list-create"),
    # 상세 조회 / 삭제 (recruitment_id 기준)
    path("<int:recruitment_id>/", BookmarkRetrieveDestroyAPIView.as_view(), name="bookmark-detail-destroy"),
]
