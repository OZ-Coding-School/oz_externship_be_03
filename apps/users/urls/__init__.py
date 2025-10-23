from django.urls import URLPattern, URLResolver

from apps.users.urls.auth_urls import urlpatterns as auth_urls
from apps.users.urls.user_withdrawal_urls import urlpatterns as user_withdrawal_urls
from apps.users.urls.user_urls import urlpatterns as users_urls

app_name = "users"

urlpatterns: list[URLPattern | URLResolver] = [
    *users_urls,
    *user_withdrawal_urls,
    *auth_urls,
]
