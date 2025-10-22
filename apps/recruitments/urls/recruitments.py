from django.urls import path

from apps.recruitments.views.recruitments import (
    RecruitmentListCreateAPIView,
    RecruitmentRetrieveUpdateDestroyAPIView,
)

urlpatterns = [
    path("", RecruitmentListCreateAPIView.as_view(), name="recruitment-list-create"),
    path(
        "<int:recruitment_id>/",
        RecruitmentRetrieveUpdateDestroyAPIView.as_view(),
        name="recruitment-detail",
    ),
]
