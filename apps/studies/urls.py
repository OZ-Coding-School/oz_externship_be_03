from django.urls import path

from apps.studies.views.groups import (
    StudyGroupDetailUpdateView,
    StudyGroupListCreateView,
)
from apps.studies.views.members import (
    DelegateLeaderView,
    MemberKickView,
    MemberLeaveView,
)
from apps.studies.views.notes import (
    StudyNoteCreateAPIView,
    StudyNoteDetailAPIView,
    StudyNoteListAPIView,
)
from apps.studies.views.reviews import GroupReviewListCreateView, GroupReviewUpdateView
from apps.studies.views.schedules import GroupScheduleCreateView

app_name = "studies"


urlpatterns = [
    # 스터디 그룹 목록 조회 및 생성
    path("groups", StudyGroupListCreateView.as_view(), name="study-group-list-create"),
    # 스터디 그룹 상세 조회 및 수정, 삭제
    path("groups/<uuid:group_uuid>", StudyGroupDetailUpdateView.as_view(), name="study-group-detail-update"),
    # 특정 스터디 그룹의 리뷰 목록 조회 및 생성
    path("groups/<uuid:group_uuid>/reviews", GroupReviewListCreateView.as_view(), name="group-reviews"),
    path(
        "groups/<uuid:group_uuid>/reviews/<uuid:review_uuid>",
        GroupReviewUpdateView.as_view(),
        name="group-review-detail",
    ),
    # 특정 스터디 그룹에 대해서 리더 권한 위임
    path(
        "groups/<uuid:group_uuid>/delegate-leader",
        DelegateLeaderView.as_view(),
        name="delegate-leader",
    ),
    # REQ-STDY-007: 그룹 탈퇴
    path(
        "groups/<uuid:group_uuid>/leave",
        MemberLeaveView.as_view(),
        name="study-member-leave",
    ),
    # REQ-STDY-006: 스터디 그룹 멤버 추방 API
    path(
        "groups/<uuid:group_uuid>/members/<int:member_id>",
        MemberKickView.as_view(),
        name="study-member-kick",
    ),
    # Schedule APIs
    path("study-schedules", GroupScheduleCreateView.as_view(), name="study-schedules-create"),
    # StudyNote APIs
    path(
        "groups/<uuid:group_id>/notes",
        StudyNoteListAPIView.as_view(),
        name="study-note-list",
    ),
    path(
        "notes",
        StudyNoteCreateAPIView.as_view(),
        name="study-note-create",
    ),
    path(
        "notes/<int:note_id>",
        StudyNoteDetailAPIView.as_view(),
        name="study-note-detail",
    ),
]
