from django.urls import path

from apps.users.views.social_auth_views import KakaoAuthView, NaverAuthView

app_name = "users"

urlpatterns = [
    path("auth/kakao/callback", KakaoAuthView.as_view(), name="kakao-login"),
    path("auth/naver/callback", NaverAuthView.as_view(), name="naver-login"),
]
