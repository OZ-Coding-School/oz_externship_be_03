from django.urls import path

from apps.recruitments.views.application import (
    ApplicationAPIView,
    ApplicationStatusUpdateAPIView,
    ApplicationListCreateAPIView,
    ApplicationWithdrawAPIView,
)

urlpatterns = [
    path("", ApplicationAPIView.as_view(), name="application-list-create"),
    path("<int:application_id>/status/", ApplicationStatusUpdateAPIView.as_view(), name="application-status-update"),
    path("applications/", ApplicationListCreateAPIView.as_view(), name="application-list-create"),
    path("applications/<int:pk>/withdraw/", ApplicationWithdrawAPIView.as_view(), name="application-withdraw"),
]
