from django.conf import settings
from django.db import models

from apps.core.models import BaseModel  # 생성/수정 시간 자동 기록 (created_at, updated_at)
from apps.studies.models.groups import StudyGroup


# 스터디 노트 모델
class StudyNote(BaseModel):
    study_group = models.ForeignKey(
        StudyGroup,
        on_delete=models.CASCADE,  # 그룹이 삭제되면 노트도 같이 삭제되게
        related_name="notes",  # 그룹이랑 연결할 때 쓰는 반대 이름
    )

    # 누가 작성했는지 (User 연결)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,  # 작성자가 탈퇴상태 유저로 전환되며 user_id -> null이 되면 CASCADE
        related_name="study_notes",  # user.study_notes 이런 식으로 접근 가능
        null=False,  # mock 단계에서만 True / 서비스화에서 False로 변경
        blank=False,
    )

    # 노트 기본 내용
    title = models.CharField(max_length=255)  # 노트 제목 (최대 255자)
    content = models.TextField()  # 실제 학습 내용 작성하는 부분
    ai_summary = models.TextField(null=True, blank=True)  # AI 요약 (오약 오류가 노트자체에 문제야기함으로 Ture)

    class Meta:
        db_table = "study_notes"  # DB 테이블 이름 지정 (ERD랑 맞춤)
        ordering = ["-created_at"]  # 최신순으로 정렬해서 조회됨

    def __str__(self) -> str:
        return f"[{self.study_group.name}] {self.title} by {self.author}"


# 노트에 달린 이미지 저장용 테이블
class StudyNoteImage(BaseModel):
    study_note = models.ForeignKey(
        StudyNote,
        on_delete=models.CASCADE,  # 노트 삭제되면 이미지도 같이 삭제
        related_name="images",  # note.images 이런 식으로 접근 가능
    )
    img_url = models.CharField(max_length=255)  # 이미지 주소 (S3 같은 곳에 저장된 경로)

    class Meta:
        db_table = "study_note_images"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Image for Note {self.study_note.id}"


# 노트에 첨부된 파일 (예: PDF, 문서 등)
class StudyNoteAttachment(BaseModel):
    study_note = models.ForeignKey(
        StudyNote,
        on_delete=models.CASCADE,  # 노트 삭제되면 첨부파일도 같이 삭제
        related_name="attachments",  # note.attachments 로 접근 가능
    )
    file_url = models.CharField(max_length=255)  # 파일 저장된 경로
    file_name = models.CharField(max_length=255)  # 실제 파일 이름 (확장자 포함)

    class Meta:
        db_table = "study_note_attachments"  # ERD 기준으로 테이블명 통일
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Attachment for Note {self.study_note.id}"
