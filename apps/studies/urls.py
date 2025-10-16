from django.urls import path

from . import views

urlpatterns = [
    path("groups", views.StudyGroupListView.as_view()),  # REQ-STDY-004
    path("groups/create", views.StudyGroupCreateView.as_view()),  # REQ-STDY-001
    path("groups/<int:group_id>", views.StudyGroupDetailView.as_view()),  # REQ-STDY-005
    path("groups/<int:group_id>/update", views.StudyGroupUpdateView.as_view()),  # REQ-STDY-009
    path("groups/date-constraint", views.StudyGroupDateConstraintView.as_view()),  # REQ-STDY-003
    # 스터디 멤버 관리
    path("groups/<int:group_id>/members/<int:member_id>/kick", views.StudyMemberKickView.as_view()),  # REQ-STDY-006
    path(
        "groups/<int:group_id>/members/<int:member_id>/delegate", views.StudyMemberDelegateView.as_view()
    ),  # REQ-STDY-008
    path("groups/<int:group_id>/leave", views.StudyMemberLeaveView.as_view()),  # REQ-STDY-007
    path("lectures", views.StudyLectureListView.as_view()),  # REQ-STDY-002
    path("scheduler/status-update", views.StudyGroupStatusAutoUpdateView.as_view()),  # REQ-STDY-010
    path("admin/groups", views.AdminStudyGroupListView.as_view()),  # REQ-STDY-011
    path("admin/groups/<int:group_id>", views.AdminStudyGroupDetailView.as_view()),  # REQ-STDY-012
]
