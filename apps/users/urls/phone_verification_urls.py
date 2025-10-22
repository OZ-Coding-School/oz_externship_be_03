from django.urls import path

from apps.users.views.phone_verification_views import (
    ChangePhoneConfirmCodeView,
    ChangePhoneSendCodeView,
    FindEmailConfirmCodeView,
    FindEmailSendCodeView,
    SignupConfirmCodeView,
    SignupSendCodeView,
)

app_name = "phone_verifications"

urlpatterns = [
    path("phone/verifications/signup/send-code", SignupSendCodeView.as_view(), name="signup_send_code"),
    path("phone/verifications/signup/confirm-code", SignupConfirmCodeView.as_view(), name="signup_confirm_code"),
    path("phone/verifications/find-email/send-code", FindEmailSendCodeView.as_view(), name="find_email_send_code"),
    path(
        "phone/verifications/find-email/confirm-code",
        FindEmailConfirmCodeView.as_view(),
        name="find_email_confirm_code",
    ),
    path(
        "phone/verifications/phone-change/send-code", ChangePhoneSendCodeView.as_view(), name="change_phone_send_code"
    ),
    path(
        "phone/verifications/phone-change/confirm-code",
        ChangePhoneConfirmCodeView.as_view(),
        name="change_phone_confirm_code",
    ),
]
