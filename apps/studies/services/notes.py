from __future__ import annotations

from datetime import timedelta
from typing import Any, Optional

from django.utils import timezone

from apps.studies.models.notes import StudyNote


class StudyNoteService:
    """
    StudyNote 관련 CRUD 및 요약 로직을 관리하는 통합 서비스 계층.
    """

    # Mock (임시 더미 데이터)
    @staticmethod
    def create_mock(title: str, content: str) -> StudyNote:
        now = timezone.now()
        return StudyNote(
            id=1,
            title=title,
            content=content,
            ai_summary="요약이 여기에 들어갑니다.",
            created_at=now,
            updated_at=now,
        )

    @staticmethod
    def get_mock_list(count: int = 5) -> list[StudyNote]:
        now = timezone.now()
        return [
            StudyNote(
                id=i,
                title=f"Mock Study Note {i}",
                content="Mock content for Study Note",
                ai_summary=f"요약 내용 {i}",
                created_at=now - timedelta(days=i),
                updated_at=now - timedelta(days=i),
            )
            for i in range(1, count + 1)
        ]

    @staticmethod
    def get_mock(note_id: int) -> StudyNote:
        now = timezone.now()
        return StudyNote(
            id=note_id,
            title="Mock Study Note",
            content="Mock Content",
            ai_summary="요약 내용",
            created_at=now - timedelta(days=1),
            updated_at=now,
        )

    # CRUD 유틸 (실제 DB 로직 전환 예정)
    @staticmethod
    def update_mock(note_id: int, title: Optional[str] = None, content: Optional[str] = None) -> StudyNote:
        now = timezone.now()
        return StudyNote(
            id=note_id,
            title=title or "기존 제목",
            content=content or "기존 내용",
            ai_summary="수정된 요약",
            created_at=now - timedelta(days=1),
            updated_at=now,
        )

    @staticmethod
    def delete_mock(note_id: int) -> None:
        return None

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
