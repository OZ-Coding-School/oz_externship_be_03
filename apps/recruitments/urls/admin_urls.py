from django.urls import path

from apps.recruitments.views.admin_views import (
    AdminRecruitmentDetailAPIView,
    AdminRecruitmentListAPIView,
)

urlpatterns = [
    path("", AdminRecruitmentListAPIView.as_view(), name="admin-recruitment-list"),
    path("<int:recruitment_id>", AdminRecruitmentDetailAPIView.as_view(), name="admin-recruitment-detail"),
]
