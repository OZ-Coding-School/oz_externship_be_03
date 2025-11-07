from django.urls import path

from apps.users.views.social_auth_views import SocialAuthView

app_name = "users"

urlpatterns = [
    path("auth/social/<str:provider>", SocialAuthView.as_view(), name="social-login"),
]
