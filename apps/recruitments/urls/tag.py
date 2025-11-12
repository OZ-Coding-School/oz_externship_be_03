from django.urls import path

from apps.recruitments.views.tag import (
    RecruitmentTagSearchAddForRecruitmentAPIView,
    RecruitmentTagSearchCreateAPIView,
)

urlpatterns = [
    path("", RecruitmentTagSearchCreateAPIView.as_view(), name="tags-search-create"),  # REQ-RECM-002
    path(
        "/<int:recruitment_id>", RecruitmentTagSearchAddForRecruitmentAPIView.as_view(), name="tags-search-add"
    ),  # REQ-RECM-008
]
