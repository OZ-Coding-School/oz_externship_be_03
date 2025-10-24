from __future__ import annotations

from datetime import timedelta
from typing import Any, Optional

from django.utils import timezone

from apps.studies.models.notes import StudyNote


class StudyNoteService:
    """
    StudyNote 관련 Mock 및 실제 생성/조회 로직을 관리하는 서비스 계층.
    """

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
        # 실제 DB 삭제 로직으로 대체될 예정
        return None


class StudyNoteSummaryService:
    """
    학습 노트 요약 생성 / 조회 관련 로직 담당.
    추후 AI Summarization API 연동 포인트.
    """

    @staticmethod
    def get_summary(note: StudyNote) -> StudyNote:
        note.ai_summary = "요약 내용입니다."
        note.updated_at = timezone.now()
        return note
