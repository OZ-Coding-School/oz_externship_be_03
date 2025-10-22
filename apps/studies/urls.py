from django.urls import path

from apps.studies.views.reviews import ReviewCreateView

app_name = "studies"

urlpatterns = [
    # POST /api/v1/studies/groups/{group_id}/reviews/
    path("studies/groups/<uuid:group_id>/reviews/", ReviewCreateView.as_view(), name="group-review-create"),
]
