from django.urls import path

from apps.studies.views.schedules import (
    GroupScheduleDetailUpdateDeleteView,
    GroupScheduleListCreateView,
)

urlpatterns = [
    path(
        "groups/<uuid:group_uuid>/schedules",
        GroupScheduleListCreateView.as_view(),
        name="group-schedule-list-create",
    ),
    path(
        "groups/<uuid:group_uuid>/schedules/<uuid:schedule_uuid>",
        GroupScheduleDetailUpdateDeleteView.as_view(),
        name="group-schedule-detail-update-delete",
    ),
]
