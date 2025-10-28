from django.urls import URLPattern, URLResolver, path

from apps.users.views.user_profile_views import MeView, UserDupNicknameView, UserProfileUpdateView, UserChangePasswordView
from apps.users.views.user_signup_views import UserSignupView
from apps.users.views.user_withdrawals_views import UserWithdrawalAPIView, UserAccountRecoveryAPIView

urlpatterns: list[URLPattern | URLResolver] = [
    path("users/", UserSignupView.as_view(), name="signup"),  # /api/v1/users/
    path("users/me/", MeView.as_view(), name="me"),  # /api/v1/users/me/

    # withdrawal
    path("users/withdraw", UserWithdrawalAPIView.as_view(), name="user_withdrawal"),
    path("users/recovery-account", UserAccountRecoveryAPIView.as_view(), name="user_recovery_account"),

    # profile update
    path("users/update-profile", UserProfileUpdateView.as_view(), name="user_update_profile"),
    path("users/change-password", UserChangePasswordView.as_view(), name="user_change_password"),
    path("users", UserSignupView.as_view(), name="signup"),  # /api/v1/users/
    path("users/me", MeView.as_view(), name="me"),  # /api/v1/users/me/
    path("users/dup-nickname", UserDupNicknameView.as_view(), name="dup_nickname"),
]
