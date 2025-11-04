from django.urls import path

from apps.recruitments.views.application import (
    ApplicationListCreateAPIView,
    ApplicationWithdrawAPIView,
)

urlpatterns = [
    path("applications/", ApplicationListCreateAPIView.as_view(), name="application-list-create"),
    path("applications/<int:pk>/withdraw/", ApplicationWithdrawAPIView.as_view(), name="application-withdraw"),
]
