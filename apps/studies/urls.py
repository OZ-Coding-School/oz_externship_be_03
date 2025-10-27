from django.urls import path

from apps.studies.views.groups import (
    StudyGroupDetailUpdateView,
    StudyGroupListCreateView,
)
from apps.studies.views.members import (
    DelegateLeaderAPIView,
    MemberKickAPIView,
    MemberLeaveAPIView,
)
from apps.studies.views.reviews import GroupReviewListView, ReviewCreateView

app_name = "studies"


urlpatterns = [
    # POST /api/v1/studies/groups/{group_id}/reviews/
    path("groups/<int:group_id>/reviews/", ReviewCreateView.as_view(), name="group-review-create"),
    # REQ-STDY-006: 스터디 그룹 리더 위임 API
    path(
        "groups/<uuid:group_id>/delegate-leader",
        DelegateLeaderAPIView.as_view(),
        name="delegate-leader",
    ),
    # REQ-STDY-007: 그룹 탈퇴
    path(
        "groups/<uuid:group_id>/leave",
        MemberLeaveAPIView.as_view(),
        name="study-member-leave",
    ),
    # REQ-STDY-006: 스터디 그룹 멤버 추방 API
    path(
        "groups/<uuid:group_id>/members/<int:member_id>",
        MemberKickAPIView.as_view(),
        name="study-member-kick",
    ),
    path("groups/", StudyGroupListCreateView.as_view(), name="study-group-list-create"),
    path("groups/<uuid:group_id>/", StudyGroupDetailUpdateView.as_view(), name="study-group-detail-update"),
]
