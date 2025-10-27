from django.urls import path

from apps.users.views.user_withdrawals_views import (
    UserAccountRecoveryAPIView,
    UserWithdrawalAPIView,
)

urlpatterns = [
    path("users/withdraw", UserWithdrawalAPIView.as_view(), name="user_withdrawal"),
    path("users/recovery-account", UserAccountRecoveryAPIView.as_view(), name="user_recovery_account"),
]
