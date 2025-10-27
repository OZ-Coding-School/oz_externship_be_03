from django.urls import URLPattern, URLResolver, include, path

from apps.users.urls.auth_urls import urlpatterns as auth_urls
from apps.users.urls.user_withdrawal_urls import urlpatterns as user_withdrawal_urls

app_name = "users"

urlpatterns: list[URLPattern | URLResolver] = [
    *auth_urls,
    *user_withdrawal_urls,
]
