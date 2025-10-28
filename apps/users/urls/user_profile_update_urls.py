from django.urls import path

from apps.users.views.user_profile_update_views import (
    UserChangePasswordView,
    UserProfileUpdateView,
)

urlpatterns = [
    path("users/update-profile", UserProfileUpdateView.as_view(), name="user_update_profile"),
    path("users/change-password", UserChangePasswordView.as_view(), name="user_change_password"),
]
