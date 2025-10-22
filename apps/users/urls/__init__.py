from django.urls import URLPattern, URLResolver, include, path

from apps.users.urls.phone_verification_urls import (
    urlpatterns as phone_verification_urls,
)

app_name = "users"

urlpatterns: list[URLPattern | URLResolver] = [
    *phone_verification_urls,
]
