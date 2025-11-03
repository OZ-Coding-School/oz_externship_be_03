from __future__ import annotations

from datetime import timedelta
from typing import Any, Optional

from django.utils import timezone

from apps.studies.models.notes import StudyNote


class StudyNoteService:

    # AI 요약 class 통합
    @staticmethod
    def summarize(note: StudyNote) -> StudyNote:
        """
        AI 요약 로직 (현재 Mock).
        추후 실제 Summarization API 호출 로직으로 대체될 예정.
        """
        note.ai_summary = "요약 내용입니다."
        note.updated_at = timezone.now()
        return note
