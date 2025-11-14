from django.urls import path

from apps.recruitments.views.recruitments import (
    RecruitmentPresignedURLAPIView,  # 🔥 presigned-url view 추가
)
from apps.recruitments.views.recruitments import (
    RecruitmentDetailUpdateDeleteAPIView,
    RecruitmentListCreateAPIView,
    RecruitmentUserListAPIView,
)

app_name = "recruitments"

urlpatterns = [
    path("", RecruitmentListCreateAPIView.as_view(), name="list-create"),
    path("mine", RecruitmentUserListAPIView.as_view(), name="user-list"),
    path(
        "<uuid:recruitment_uuid>",
        RecruitmentDetailUpdateDeleteAPIView.as_view(),
        name="detail",
    ),  # REQ-RECM-006,007,009
    path("presigned-url", RecruitmentPresignedURLAPIView.as_view(), name="presigned-url"),
]
