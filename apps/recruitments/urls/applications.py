from django.urls import path

from apps.recruitments.views.application_views import ApplicationCreateAPIView
from apps.recruitments.views.application_withdrawal_views import (
    ApplicationWithdrawAPIView,
)
from apps.recruitments.views.application_views import (
    ApplicationApproveAPIView,
    ApplicationCreateAPIView,
    ApplicationDetailAPIView,
    ApplicationListAPIView,
    ApplicationRejectAPIView,
)
from apps.recruitments.views.my_application_views import (
    MyApplicationDetailAPIView,
    MyApplicationsAPIView,
)

urlpatterns = [
    path(
        "/<uuid:recruitment_uuid>/applications",
        ApplicationCreateAPIView.as_view(),
        name="recruitment-application-create",
    ),
    path("/applications/me", MyApplicationsAPIView.as_view(), name="my-applications"),
    path(
        "/applications/me/<uuid:application_uuid>", MyApplicationDetailAPIView.as_view(), name="my-application-detail"
    ),
    path(
        "/applications/<uuid:application_uuid>/withdraw",
        ApplicationWithdrawAPIView.as_view(),
        name="application-withdraw",
    ),
    path(
        "/<str:recruitment_uuid>/applications/list",
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
