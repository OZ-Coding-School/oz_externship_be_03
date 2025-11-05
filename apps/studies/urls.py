from django.urls import path

from apps.studies.views.groups import (
    AdminStudyGroupDetailView,
    AdminStudyGroupListView,
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
from apps.studies.views.s3_studies import (
    StudyGroupS3PresignedView,
    StudyNoteS3PresignedView,
)
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
    # 스터디 그룹 멤버 추방 API
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
    # 어드민 스터디그룹 목록조회
    path(
        "admin/groups",
        AdminStudyGroupListView.as_view(),
        name="admin-study-group-list",
    ),
    # 어드민 스터디그룹 상세조회
    path(
        "admin/groups/<uuid:group_uuid>",
        AdminStudyGroupDetailView.as_view(),
        name="admin-study-group-detail",
    ),
    # 그룹 대표 이미지 Presigned URL 발급
    path(
        "group/s3-presigned-url/",
        StudyGroupS3PresignedView.as_view(),
        name="study_group_s3_presigned",
    ),
    # 노트 첨부파일 / 이미지 Presigned URL 발급
    path(
        "notes/s3-presigned-url/",
        StudyNoteS3PresignedView.as_view(),
        name="study_note_s3_presigned",
    ),
]
