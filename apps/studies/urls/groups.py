from django.urls import path

from apps.studies.views import groups

urlpatterns = [
    path("groups", groups.StudyGroupListView.as_view()),  # REQ-STDY-004
    path("groups/create", groups.StudyGroupCreateView.as_view()),  # REQ-STDY-001
    path("groups/<int:group_id>", groups.StudyGroupDetailView.as_view()),  # REQ-STDY-005
    path("groups/<int:group_id>/update", groups.StudyGroupUpdateView.as_view()),  # REQ-STDY-009
    path("groups/date-constraint", groups.StudyGroupDateConstraintView.as_view()),  # REQ-STDY-003
    # 스터디 멤버 관리
    path("groups/<int:group_id>/members/<int:member_id>/kick", groups.StudyMemberKickView.as_view()),  # REQ-STDY-006
    path(
        "groups/<int:group_id>/members/<int:member_id>/delegate", groups.StudyMemberDelegateView.as_view()
    ),  # REQ-STDY-008
    path("groups/<int:group_id>/leave", groups.StudyMemberLeaveView.as_view()),  # REQ-STDY-007
    path("lectures", groups.StudyLectureListView.as_view()),  # REQ-STDY-002
    path("scheduler/status-update", groups.StudyGroupStatusAutoUpdateView.as_view()),  # REQ-STDY-010
    path("admin/groups", groups.AdminStudyGroupListView.as_view()),  # REQ-STDY-011
    path("admin/groups/<int:group_id>", groups.AdminStudyGroupDetailView.as_view()),  # REQ-STDY-012
]
