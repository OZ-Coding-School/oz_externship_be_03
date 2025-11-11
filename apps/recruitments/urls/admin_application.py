from django.urls import path
from apps.recruitments.views.admin_application import (
    AdminRecruitmentApplicationListAPIView,
    AdminApplicationDetailAPIView,
    AdminApplicationStatusUpdateAPIView,
)

urlpatterns = [
    path("admin/applications/", AdminRecruitmentApplicationListAPIView.as_view(), name="admin-application-list"),
    path("admin/applications/<int:pk>/", AdminApplicationDetailAPIView.as_view(), name="admin-application-detail"),
    path("admin/applications/<int:pk>/status/", AdminApplicationStatusUpdateAPIView.as_view(), name="admin-application-status"),
]