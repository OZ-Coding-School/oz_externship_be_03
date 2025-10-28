from django.urls import path

from apps.users.views.password_reset_views import PasswordResetView

urlpatterns = [
    path("users/reset-password", PasswordResetView.as_view(), name="user_reset_password"),
]
