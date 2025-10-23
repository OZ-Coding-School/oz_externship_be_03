from django.urls import path

from apps.users.views.user_withdrawals_views import (
    UserAccountRecoveryAPIView,
    UserWithdrawalAPIView,
)

urlpatterns = [
    path("me/withdraw", UserWithdrawalAPIView.as_view(), name="user_withdrawal"),
    path("recovery/account", UserAccountRecoveryAPIView.as_view(), name="user_account_recovery"),
]
