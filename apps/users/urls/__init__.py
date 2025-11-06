from django.urls import URLPattern, URLResolver

from apps.users.urls.admin_urls import urlpatterns as admin_urls
from apps.users.urls.auth_urls import urlpatterns as auth_urls
from apps.users.urls.user_urls import urlpatterns as users_urls
from apps.users.urls.social_urls import urlpatterns as social_urls

app_name = "users"

urlpatterns: list[URLPattern | URLResolver] = [
    *users_urls,
    *auth_urls,
    *admin_urls,
    *social_urls
]
