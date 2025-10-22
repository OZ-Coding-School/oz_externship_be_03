from django.urls import path

from apps.studies.views.members import DelegateLeaderAPIView

urlpatterns = [
    # REQ-STDY-006: 스터디 그룹 리더 위임 API
    path(
        "groups/<uuid:group_id>/delegate-leader",
        DelegateLeaderAPIView.as_view(),
        name="delegate-leader",
    )
]
