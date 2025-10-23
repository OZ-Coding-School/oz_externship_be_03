from django.urls import URLPattern, URLResolver, include, path

from apps.users.urls.auth_urls import urlpatterns as auth_urls

app_name = "users"

urlpatterns: list[URLPattern | URLResolver] = [
    *auth_urls,
]
