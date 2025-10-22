from django.urls import path

from apps.users.views.phone_verification_views import (
    ChangePhoneConfirmCodeView,
    ChangePhoneSendCodeView,
    PublicPhoneConfirmCodeView,
    PublicPhoneSendCodeView,
)

app_name = "phone_verifications"

urlpatterns = [
    # Public
    path("phone/verifications/public/send-code", PublicPhoneSendCodeView.as_view(), name="public_send_code"),
    path("phone/verifications/public/confirm-code", PublicPhoneConfirmCodeView.as_view(), name="public_confirm_code"),
    # Auth
    path(
        "phone/verifications/change-phone/send-code", ChangePhoneSendCodeView.as_view(), name="change_phone_send_code"
    ),
    path(
        "phone/verifications/change-phone/confirm-code",
        ChangePhoneConfirmCodeView.as_view(),
        name="change_phone_confirm_code",
    ),
]
