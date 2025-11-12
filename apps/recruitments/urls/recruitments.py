from django.urls import path

from apps.recruitments.views.application_views import ApplicationCreateAPIView
from apps.recruitments.views.my_application_views import MyApplicationsAPIView
from apps.recruitments.views.recruitments import (
    RecruitmentDetailUpdateDeleteAPIView,
    RecruitmentListCreateAPIView,
    RecruitmentUserListAPIView,
)

urlpatterns = [
    path("", RecruitmentListCreateAPIView.as_view(), name="list-create"),  # REQ-RECM-001,003
    path(
        "<uuid:recruitment_uuid>/applications",
        ApplicationCreateAPIView.as_view(),
        name="recruitment-application-create",
    ),
    path(
        "/<int:recruitment_id>", RecruitmentDetailUpdateDeleteAPIView.as_view(), name="detail"
    ),  # REQ-RECM-006,007,009
    path("/users/<int:user_id>", RecruitmentUserListAPIView.as_view(), name="user-list"),  # REQ-RECM-005
    path("applications/me", MyApplicationsAPIView.as_view(), name="my-applications"),
]
