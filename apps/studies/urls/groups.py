from django.urls import path

from apps.studies.views.groups import (
    StudyGroupDetailUpdateView,
    StudyGroupListCreateView,
)

urlpatterns = [
    path("groups", StudyGroupListCreateView.as_view(), name="study-group-list-create"),
    path("groups/<uuid:group_uuid>", StudyGroupDetailUpdateView.as_view(), name="study-group-detail-update"),
]
