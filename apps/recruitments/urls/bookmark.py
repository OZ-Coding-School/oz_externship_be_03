from django.urls import path

from apps.recruitments.views.bookmark import (
    RecruitmentBookmarkedListAPIView,
    RecruitmentBookmarkToggleAPIView,
)

urlpatterns = [
    path("/<int:recruitment_id>", RecruitmentBookmarkToggleAPIView.as_view(), name="bookmark-toggle"),  # REQ-RECM-010
    path("", RecruitmentBookmarkedListAPIView.as_view(), name="bookmark-list"),  # REQ-RECM-011
]
