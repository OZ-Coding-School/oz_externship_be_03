from django.urls import path

from apps.recruitments.views.application_views import (
    ApplicationApproveAPIView,
    ApplicationDetailAPIView,
    ApplicationListAPIView,
    ApplicationRejectAPIView,
)

urlpatterns = [
    path(
        "/<str:recruitment_uuid>/applications",
        ApplicationListAPIView.as_view(),
        name="application-list",
    ),
    path(
        "/applications/<str:application_uuid>",
        ApplicationDetailAPIView.as_view(),
        name="application-detail",
    ),
    path(
        "/applications/<str:application_uuid>/approve",
        ApplicationApproveAPIView.as_view(),
        name="application-approve",
    ),
    path(
        "/applications/<str:application_uuid>/reject",
        ApplicationRejectAPIView.as_view(),
        name="application-reject",
    ),
]
