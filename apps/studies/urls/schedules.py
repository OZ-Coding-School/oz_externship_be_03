from django.urls import path
from apps.studies.views.schedules import (
    StudyScheduleListCreateView,
    StudyScheduleDetailView,
)

urlpatterns = [
    # 스터디 일정 목록 조회 + 생성
    path(
        "groups/<uuid:group_id>/schedules/",
        StudyScheduleListCreateView.as_view(),
        name="study-schedule-list-create",
    ),
    # 스터디 일정 상세 조회, 수정, 삭제
    path(
        "groups/<uuid:group_id>/schedules/<int:schedule_id>/",
        StudyScheduleDetailView.as_view(),
        name="study-schedule-detail",
    ),
]
