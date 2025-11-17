from django.urls import URLPattern, URLResolver, path

from apps.users.views.find_email_views import FindEmailView
from apps.users.views.password_reset_views import PasswordResetView
from apps.users.views.user_profile_views import (
    MeView,
    UserChangePasswordView,
    UserDupNicknameView,
    UserProfileUpdateView,
)
from apps.users.views.user_signup_views import UserSignupView
from apps.users.views.user_withdrawals_views import (
    UserAccountRecoveryAPIView,
    UserWithdrawalAPIView,
)

urlpatterns: list[URLPattern | URLResolver] = [
    # --------------------------------------------------------
    # 회원가입 및 기본 프로필
    # --------------------------------------------------------
    path("users", UserSignupView.as_view(), name="signup"),
    path("users/me", MeView.as_view(), name="me"),
    # --------------------------------------------------------
    # 프로필 및 계정 관리
    # --------------------------------------------------------
    path("users/update-profile", UserProfileUpdateView.as_view(), name="user_update_profile"),
    path("users/change-password", UserChangePasswordView.as_view(), name="user_change_password"),
    path("users/dup-nickname", UserDupNicknameView.as_view(), name="dup_nickname"),
    # --------------------------------------------------------
    # 비밀번호 / 계정 복구
    # --------------------------------------------------------
    path("users/reset-password", PasswordResetView.as_view(), name="user_reset_password"),
    path("users/find-email", FindEmailView.as_view(), name="user_find_email"),
    path("users/recovery-account", UserAccountRecoveryAPIView.as_view(), name="user_recovery_account"),
    # --------------------------------------------------------
    # 회원 탈퇴
    # --------------------------------------------------------
    path("users/withdraw", UserWithdrawalAPIView.as_view(), name="user_withdrawal"),
]
