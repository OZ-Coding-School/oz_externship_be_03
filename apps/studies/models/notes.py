from django.conf import settings
from django.db import models
#from apps.studies.models.groups import StudyGroup #그룹연결하면 주석 삭제할겁니다

from apps.core.models import BaseModel  # 생성/수정 시간 자동 기록 (created_at, updated_at)


class StudyNote(BaseModel):
    study_group = models.ForeignKey(
        StudyGroup,
        on_delete=models.CASCADE,  # 그룹 삭제되면 노트도 같이 삭제
        related_name="notes",
    )
    # 누가 작성했는지 연결
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,  # 작성자 삭제되면 노트도 같이 삭제
        related_name="study_notes",
    )
    title = models.CharField(max_length=255)  # 노트 제목
    content = models.TextField()  # 노트 내용
    ai_summary = models.TextField()  # AI요약 필수로 넣게

    class Meta:
        db_table = "study_notes"  # 테이블 이름 맞춰줌
        ordering = ["-created_at"]  # 최신순 정렬

    def __str__(self):
        # 보기 쉽게 그룹 이름, 제목, 작성자 표시
        return f"[{self.study_group.name}] {self.title} by {self.author}"


class StudyNoteImage(BaseModel):
    study_note = models.ForeignKey(
        StudyNote,
        on_delete=models.CASCADE,  # 노트가 삭제되면 이미지도 같이 삭제
        related_name="images",
    )
    img_url = models.CharField(max_length=255)  # 이미지 파일 주소

    class Meta:
        db_table = "study_note_images"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Image for Note {self.study_note.id}"


class StudyNoteAttachment(BaseModel):
    study_note = models.ForeignKey(
        StudyNote,
        on_delete=models.CASCADE,  # 노트 삭제되면 파일도 같이 삭제
        related_name="attachments",
    )
    file_url = models.CharField(max_length=255)  # 파일이 저장된 주소
    file_name = models.CharField(max_length=255)  # 파일명 (확장자 포함)

    class Meta:
        db_table = "study_note_attachments"  # ERD에 있는 그대로 써야 돼서 이렇게 지정
        ordering = ["-created_at"]

    def __str__(self):  # 어드민 페이지에서 볼기 편하게
        return f"Attachment for Note {self.study_note.id}"
