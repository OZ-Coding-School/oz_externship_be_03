from django.urls import path

from apps.studies.views.specs.notes import (
    StudyNoteListCreateAPIView,
    StudyNoteRetrieveUpdateDestroyAPIView,
    StudyNoteSummaryAPIView,
)

urlpatterns = [
    # 학습 기록 전체조회(GET) + 작성(POST)
    path("notes/", StudyNoteListCreateAPIView.as_view(), name="studynote-list"),
    # 단일 조회/수정/삭제
    path("notes/<int:note_id>/", StudyNoteRetrieveUpdateDestroyAPIView.as_view(), name="studynote-detail"),
    # 요약 조회
    path("notes/<int:note_id>/summary/", StudyNoteSummaryAPIView.as_view(), name="studynote-summary"),
]
