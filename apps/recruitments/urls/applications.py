from django.urls import path

from apps.recruitments.views.application_views import ApplicationCreateAPIView
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
    path("/applications/me/<uuid:application_uuid>", MyApplicationDetailAPIView.as_view(), name="my-application-detail"),
]
