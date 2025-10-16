from django.urls import include, path

app_name = "studies"

urlpatterns = [
    path("groups/<uuid:group_id>/reviews/", include("apps.studies.urls.reviews")),
]
