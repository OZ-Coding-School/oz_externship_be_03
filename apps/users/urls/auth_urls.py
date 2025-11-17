from django.urls import path

from apps.users.views.auth_views import LoginView, LogoutView, TokenRefreshView
from apps.users.views.email_verification_views import (
    ChangeEmailConfirmCodeView,
    ChangeEmailSendCodeView,
    ResetPasswordEmailConfirmCodeView,
    ResetPasswordEmailSendCodeView,
    RestoreUserEmailConfirmCodeView,
    RestoreUserEmailSendCodeView,
    SignupEmailConfirmCodeView,
    SignupEmailSendCodeView,
)
from apps.users.views.phone_verification_views import (
    ChangePhoneConfirmCodeView,
    ChangePhoneSendCodeView,
    FindEmailConfirmCodeView,
    FindEmailSendCodeView,
    SignupConfirmCodeView,
    SignupSendCodeView,
)

urlpatterns = [
    path("phone-verifications/signup/send-code", SignupSendCodeView.as_view(), name="phone_signup_send_code"),
    path("phone-verifications/signup/confirm-code", SignupConfirmCodeView.as_view(), name="phone_signup_confirm_code"),
    path("phone-verifications/find-email/send-code", FindEmailSendCodeView.as_view(), name="find_email_send_code"),
    path(
        "phone-verifications/find-email/confirm-code",
        FindEmailConfirmCodeView.as_view(),
        name="find_email_confirm_code",
    ),
    path(
        "phone-verifications/phone-change/send-code", ChangePhoneSendCodeView.as_view(), name="change_phone_send_code"
    ),
    path(
        "phone-verifications/phone-change/confirm-code",
        ChangePhoneConfirmCodeView.as_view(),
        name="change_phone_confirm_code",
    ),
    path("email-verifications/signup/send-code", SignupEmailSendCodeView.as_view(), name="email_signup_send_code"),
    path(
        "email-verifications/signup/confirm-code",
        SignupEmailConfirmCodeView.as_view(),
        name="email_signup_confirm_code",
    ),
    path(
        "email-verifications/password-reset/send-code",
        ResetPasswordEmailSendCodeView.as_view(),
        name="email_reset_password_send_code",
    ),
    path(
        "email-verifications/password-reset/confirm-code",
        ResetPasswordEmailConfirmCodeView.as_view(),
        name="email_reset_password_confirm_code",
    ),
    path(
        "email-verifications/restore-user/send-code",
        RestoreUserEmailSendCodeView.as_view(),
        name="email_restore_user_send_code",
    ),
    path(
        "email-verifications/restore-user/confirm-code",
        RestoreUserEmailConfirmCodeView.as_view(),
        name="email_restore_user_confirm_code",
    ),
    path(
        "email-verifications/email_change/send-code",
        ChangeEmailSendCodeView.as_view(),
        name="email_change_email_send_code",
    ),
    path(
        "email-verifications/email_change/confirm-code",
        ChangeEmailConfirmCodeView.as_view(),
        name="email_change_email_confirm_code",
    ),
    path("auth/login", LoginView.as_view(), name="auth_login"),
    path("auth/refresh", TokenRefreshView.as_view(), name="auth_refresh"),
    path("auth/logout", LogoutView.as_view(), name="auth_logout"),
]
