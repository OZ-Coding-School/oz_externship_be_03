from django.urls import path

from apps.studies.views.reviews import ReviewCreateView

app_name = "studies"

urlpatterns = [
    # POST /api/v1/studies/groups/{group_id}/reviews/
    path("studies/groups/<uuid:group_id>/reviews/", ReviewCreateView.as_view(), name="group-review-create"),
from apps.studies.views.members import DelegateLeaderAPIView

urlpatterns = [
    # REQ-STDY-006: 스터디 그룹 리더 위임 API
    path(
        "groups/<uuid:group_id>/delegate-leader",
        DelegateLeaderAPIView.as_view(),
        name="delegate-leader",
    )
]
