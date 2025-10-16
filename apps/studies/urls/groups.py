from django.urls import path

from apps.studies.views import groups

urlpatterns = [
    path("groups", groups.StudyGroupListView.as_view(), name="group-list"),  # REQ-STDY-004
    path("groups/create", groups.StudyGroupCreateView.as_view(), name="group-create"),  # REQ-STDY-001
    path("groups/<int:group_id>", groups.StudyGroupDetailView.as_view(), name="group-detail"),  # REQ-STDY-005
    path("groups/<int:group_id>/update", groups.StudyGroupUpdateView.as_view(), name="group-update"),  # REQ-STDY-009
    path(
        "groups/date-constraint", groups.StudyGroupDateConstraintView.as_view(), name="group-date-constraint"
    ),  # REQ-STDY-003
    path(
        "groups/<int:group_id>/members/<int:member_id>/kick",
        groups.StudyMemberKickView.as_view(),
        name="group-member-kick",
    ),  # REQ-STDY-006
    path(
        "groups/<int:group_id>/members/<int:member_id>/delegate",
        groups.StudyMemberDelegateView.as_view(),
        name="group-member-delegate",
    ),  # REQ-STDY-008
    path(
        "groups/<int:group_id>/leave", groups.StudyMemberLeaveView.as_view(), name="group-member-leave"
    ),  # REQ-STDY-007
    path(
        "groups/<int:group_id>/lectures", groups.StudyLectureListView.as_view(), name="group-lectures"
    ),  # REQ-STDY-002
    path(
        "scheduler/status-update", groups.StudyGroupStatusAutoUpdateView.as_view(), name="group-status-auto"
    ),  # REQ-STDY-010
    path("admin/groups", groups.AdminStudyGroupListView.as_view(), name="admin-group-list"),  # REQ-STDY-011
    path(
        "admin/groups/<int:group_id>", groups.AdminStudyGroupDetailView.as_view(), name="admin-group-detail"
    ),  # REQ-STDY-012
]
