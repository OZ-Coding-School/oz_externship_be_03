from django.urls import path

from apps.studies.views.members import (
    DelegateLeaderView,
    MemberKickView,
    MemberLeaveView,
)

urlpatterns = [
    # 리더 권한 위임
    path(
        "groups/<uuid:group_uuid>/delegate-leader",
        DelegateLeaderView.as_view(),
        name="delegate-leader",
    ),
    # 그룹 탈퇴
    path(
        "groups/<uuid:group_uuid>/leave",
        MemberLeaveView.as_view(),
        name="study-member-leave",
    ),
    # 스터디 그룹 멤버 추방
    path(
        "groups/<uuid:group_uuid>/kick-member",
        MemberKickView.as_view(),
        name="study-member-kick",
    ),
]
