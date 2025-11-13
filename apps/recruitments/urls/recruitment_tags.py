from django.urls import path

from apps.recruitments.views.recruitment_tag_views import (
    RecruitmentTagSearchAddForRecruitmentAPIView,
    RecruitmentTagSearchCreateAPIView,
)

urlpatterns = [
    path("/recruitments-tags", RecruitmentTagSearchCreateAPIView.as_view(), name="tags-search-create"),  # REQ-RECM-002
    path(
        "/recruitments-tags/<int:recruitment_uuid>",
        RecruitmentTagSearchAddForRecruitmentAPIView.as_view(),
        name="tags-search-add",
    ),  # REQ-RECM-008
]
