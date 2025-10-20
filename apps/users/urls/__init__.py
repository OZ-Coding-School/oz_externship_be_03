from django.urls import include, path

app_name = "users"

urlpatterns = [
    path("", include(("apps.users.urls.phone_verifications", "phone_verifications"))),
]
