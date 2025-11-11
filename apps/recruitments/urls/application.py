# 사용자용 지원서 API 라우팅
from django.urls import path
from apps.recruitments.views.application import (
    ApplicationListCreateAPIView,
    ApplicationWithdrawAPIView,
    MyApplicationListAPIView,
    MyApplicationDetailAPIView,
)

urlpatterns = [
    path("applications/", ApplicationListCreateAPIView.as_view(), name="application-list-create"),
    path("applications/<int:pk>/withdraw/", ApplicationWithdrawAPIView.as_view(), name="application-withdraw"),
    path("applications/my/", MyApplicationListAPIView.as_view(), name="application-my-list"),
    path("applications/my/<int:pk>/", MyApplicationDetailAPIView.as_view(), name="application-my-detail"),
]