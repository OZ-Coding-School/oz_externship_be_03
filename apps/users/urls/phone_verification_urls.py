from django.urls import path

from apps.users.views.phone_verification_views import (
    PhoneConfirmCodeView,
    PhoneSendCodeView,
)

app_name = "phone_verifications"

urlpatterns = [
    path("phone/verifications/send-code", PhoneSendCodeView.as_view(), name="send_code"),
    path("phone/verifications/confirm-code", PhoneConfirmCodeView.as_view(), name="confirm_code"),
]
