from django.urls import path

from apps.studies.views.members import DelegateLeaderAPIView, MemberKickAPIView

urlpatterns = [
    # REQ-STDY-008: 스터디 그룹 리더 위임 API
    path(
        "groups/<uuid:group_id>/delegate-leader",
        DelegateLeaderAPIView.as_view(),
        name="delegate-leader",
    ),
    # REQ-STDY-006: 스터디 그룹 멤버 추방 API
    path(
        "groups/<uuid:group_id>/members/<int:member_id>",
        MemberKickAPIView.as_view(),
        name="study-member-kick",
    ),
]
