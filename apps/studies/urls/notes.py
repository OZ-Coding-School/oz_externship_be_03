from django.urls import path

from apps.studies.views.notes import (
    StudyNoteCreateAPIView,
    StudyNoteDetailAPIView,
    StudyNoteListAPIView,
)
from apps.studies.views.s3_presign import (
    StudyGroupS3PresignedView,
    StudyNoteS3PresignedView,
)

urlpatterns = [
    # StudyNote APIs
    path(
        "groups/<uuid:group_uuid>/notes",
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
    # 그룹 대표 이미지 Presigned URL 발급
    path(
        "groups/presigned-url",
        StudyGroupS3PresignedView.as_view(),
        name="study_group_presigned",
    ),
    # 노트 첨부파일 / 이미지 Presigned URL 발급
    path(
        "notes/presigned-url",
        StudyNoteS3PresignedView.as_view(),
        name="study_note_presigned",
    ),
]
