from django.urls import path

from apps.studies.views.members import LeaderDelegationAPIView

urlpatterns = [
    # REQ-STDY-006: 스터디 그룹 리더 위임 API
    path(
        "groups/<uuid:group_id>/members/<int:member_id>",
        LeaderDelegationAPIView.as_view(),
        name="study-group-leader-delegate",
    ),
]
