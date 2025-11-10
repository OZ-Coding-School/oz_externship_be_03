from django.urls import path

from apps.recruitments.views.admin_application_views import (
    ApplicationAdminAPIView,
    ApplicationDetailAdminAPIView,
)
from apps.recruitments.views.admin_recruitment_views import (
    AdminRecruitmentDetailAPIView,
    AdminRecruitmentListAPIView,
)

urlpatterns = [
    path("recruitments", AdminRecruitmentListAPIView.as_view(), name="admin-recruitment-list"),
    path("recruitments/<int:recruitment_id>", AdminRecruitmentDetailAPIView.as_view(), name="admin-recruitment-detail"),
    path("applications", ApplicationAdminAPIView.as_view(), name="admin-application-list"),
    path("applications/<int:application_id>", ApplicationDetailAdminAPIView.as_view(), name="admin-application-detail"),
]
