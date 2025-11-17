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
    path(
        "recruitments/<uuid:recruitment_uuid>", AdminRecruitmentDetailAPIView.as_view(), name="admin-recruitment-detail"
    ),
    path("applications", ApplicationAdminAPIView.as_view(), name="admin-application-list"),
    path(
        "applications/<uuid:application_uuid>", ApplicationDetailAdminAPIView.as_view(), name="admin-application-detail"
    ),
]
