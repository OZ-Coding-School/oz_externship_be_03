from django.urls import path

from apps.recruitments.views.recruitments import (
    RecruitmentDetailUpdateDeleteAPIView,
    RecruitmentListCreateAPIView,
    RecruitmentUserListAPIView,
)
from apps.recruitments.views.s3_presign import RecruitmentS3PresignedView

urlpatterns = [
    path("", RecruitmentListCreateAPIView.as_view(), name="list-create"),  # REQ-RECM-001,003
    path(
        "/<uuid:recruitment_uuid>", RecruitmentDetailUpdateDeleteAPIView.as_view(), name="detail"
    ),  # REQ-RECM-006,007,009
    path("/mine", RecruitmentUserListAPIView.as_view(), name="user-list"),  # REQ-RECM-005
    path("/presigned_url", RecruitmentS3PresignedView.as_view(), name="presigned_url"),
]
