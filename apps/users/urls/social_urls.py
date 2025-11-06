from django.urls import path

from apps.users.views.social_auth_views import SocialAuthView

app_name = "users"

urlpatterns = [
    path("auth/social/kakao", SocialAuthView.as_view(), {"provider": "kakao"}, name="kakao-login"),
    path("auth/social/naver", SocialAuthView.as_view(), {"provider": "naver"}, name="naver-login"),
]
