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
from apps.studies.views.reviews import GroupReviewListCreateView
from apps.studies.views.members import DelegateLeaderAPIView
from apps.studies.views.notes import (
    StudyNoteDetailAPIView,
    StudyNoteListCreateAPIView,
)
from apps.studies.views.reviews import ReviewCreateView
from apps.studies.views.schedules import GroupScheduleCreateView

app_name = "studies"


urlpatterns = [
    # 스터디 그룹 목록 조회 및 생성
    path("groups", StudyGroupListCreateView.as_view(), name="study-group-list-create"),
    # 스터디 그룹 상세 조회 및 수정, 삭제
    path("groups/<uuid:group_id>", StudyGroupDetailUpdateView.as_view(), name="study-group-detail-update"),
    # 특정 스터디 그룹의 리뷰 목록 조회 및 생성
    path("groups/<uuid:group_id>/reviews", GroupReviewListCreateView.as_view(), name="group-reviews"),
    # 특정 스터디 그룹에 대해서 리더 권한 위임
    path(
        "groups/<uuid:group_id>/delegate-leader",
        DelegateLeaderAPIView.as_view(),
        name="delegate-leader",
    ),
    # 스터디 그룹 나가기
    path(
        "groups/<uuid:group_id>/leave",
        MemberLeaveAPIView.as_view(),
        name="study-member-leave",
    ),
    # 스터디 그룹 멤버 추방
    path(
        "groups/<uuid:group_id>/members/<int:member_id>",
        MemberKickAPIView.as_view(),
        name="study-member-kick",
    ),
    path("groups/", StudyGroupListCreateView.as_view(), name="study-group-list-create"),
    path("groups/<uuid:group_id>/", StudyGroupDetailUpdateView.as_view(), name="study-group-detail-update"),

    # StudyNote APIs
    path("notes/", StudyNoteListCreateAPIView.as_view(), name="study-note-list-create"),
    path("notes/<int:note_id>/", StudyNoteDetailAPIView.as_view(), name="study-note-detail"),
    path("groups/<uuid:group_id>/notes/", StudyNoteListCreateAPIView.as_view(), name="study-note-list-create"),
    path("groups/<uuid:group_id>/notes/<int:note_id>/", StudyNoteDetailAPIView.as_view(), name="study-note-detail"),
    path(
        "groups/<uuid:group_id>/notes/<int:note_id>/summary/",
        StudyNoteSummaryAPIView.as_view(),
        name="study-note-summary",
    ),
    # Schedule APIs
    path("study-schedules", GroupScheduleCreateView.as_view(), name="study-schedules-create"),
]
