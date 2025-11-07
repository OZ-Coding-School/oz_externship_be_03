from django.urls import path

from apps.users.views.social_auth_views import KakaoAuthView, NaverAuthView

app_name = "users"

urlpatterns = [
    path("auth/social/kakao", KakaoAuthView.as_view(), {"provider": "kakao"}, name="kakao-login"),
    path("auth/social/naver", NaverAuthView.as_view(), {"provider": "naver"}, name="naver-login"),
]
