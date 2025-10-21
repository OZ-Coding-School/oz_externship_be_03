from django.urls import path

from apps.studies.views.note_views import (
    StudyNoteListCreateAPIView,
    StudyNoteRetrieveUpdateDestroyAPIView,
    StudyNoteSummaryAPIView,
)

urlpatterns = [
    path("notes/", StudyNoteListCreateAPIView.as_view(), name="study-note-list-create"),
    path("notes/<int:note_id>/", StudyNoteRetrieveUpdateDestroyAPIView.as_view(), name="study-note-detail"),
    path("notes/<int:note_id>/summary/", StudyNoteSummaryAPIView.as_view(), name="study-note-summary"),
]
