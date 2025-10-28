from django.urls import URLPattern, URLResolver, path

from apps.users.views.user_profile_views import MeView
from apps.users.views.user_signup_views import UserSignupView

urlpatterns: list[URLPattern | URLResolver] = [
    path("users/", UserSignupView.as_view(), name="signup"),  # /api/v1/users/
    path("users/me/", MeView.as_view(), name="me"),  # /api/v1/users/me/
]
