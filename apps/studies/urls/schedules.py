from django.urls import path

from apps.studies.views.schedules import (
    GroupScheduleCreateAPIView,
    GroupScheduleDetailUpdateDeleteView,
    GroupScheduleListAPIView,
)

urlpatterns = [
    path(
        "groups/<uuid:group_uuid>/schedules",
        GroupScheduleListAPIView.as_view(),
        name="group-schedule-list",
    ),
    path(
        "schedules",
        GroupScheduleCreateAPIView.as_view(),
        name="group-schedule-create",
    ),
    path(
        "schedules/<uuid:schedule_uuid>",
        GroupScheduleDetailUpdateDeleteView.as_view(),
        name="group-schedule-detail-update-delete",
    ),
]
