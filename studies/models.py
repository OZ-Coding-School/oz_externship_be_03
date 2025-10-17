from django.conf import settings
from django.db import models

from apps.core.models import BaseModel  # 생성/수정 시간 자동 기록 (created_at, updated_at)


# 스터디 그룹 (노트가 속할 그룹)
class StudyGroup(BaseModel):
    # 그룹마다 구분할 수 있는 고유 번호 (uuid)
    uuid = models.UUIDField(unique=True, editable=False)  # 사람이 바꾸지 못핟게 하기
    name = models.CharField(max_length=20)  # 그룹 이름
    introduction = models.CharField(max_length=100)  # 그룹 소개 (설명)
    max_headcount = models.SmallIntegerField()  # 최대 인원 수
    profile_img_url = models.CharField(max_length=255, blank=True, null=True)  # 그룹 대표 이미지 (없어도 됨)

    # 스터디 상태 (예정 / 진행중 / 종료)
    class Status(models.TextChoices):
        PLANNED = "PLANNED", "예정"
        ACTIVE = "ACTIVE", "진행중"
        CLOSED = "CLOSED", "종료"

    status = models.CharField(max_length=30, choices=Status.choices)  # 현재 상태 저장

    class Meta:
        db_table = "study_groups"  # ERD 이름 그대로 테이블 이름 지정

    def __str__(self):
        # 관리자 페이지나 print()에서 이름만 보이게
        return self.name


class StudyNote(BaseModel):
    # 어떤 스터디 그룹의 노트인지 연결
    study_group = models.ForeignKey(
        StudyGroup,
        on_delete=models.CASCADE,  # 그룹 삭제되면 노트도 같이 삭제
        related_name="notes",
    )
    # 누가 작성했는지 연결 (User 모델)
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


# 노트 이미지 (노트에 들어가는 이미지)
class StudyNoteImage(BaseModel):
    # 어떤 노트에 속한 이미지인지 연결
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


# 노트 첨부파일 (노트에 들어가는 파일)
class StudyNoteAttachment(BaseModel):
    # 어떤 노트에 속한 첨부파일인지 연결
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
