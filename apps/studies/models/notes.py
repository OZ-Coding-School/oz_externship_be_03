from django.conf import settings
from django.db import models

from apps.core.models import BaseModel  # 생성/수정 시간 자동 기록 (created_at, updated_at)
# from apps.studies.models.groups import StudyGroup  # 그룹이랑 연결하면 주석 삭제할게여


# 스터디 노트 모델
class StudyNote(BaseModel):
    # 그룹 연결 (지금은 그룹 담당자분 파트라 임시로 비활성화)
    # 나중에 그룹 모델이랑 합쳐지면 아래 주석 풀면 됩니다.
    # study_group = models.ForeignKey(
    #     StudyGroup,
    #     on_delete=models.CASCADE,  # 그룹이 삭제되면 노트도 같이 삭제되게
    #     related_name="notes",  # 그룹이랑 연결할 때 쓰는 반대 이름
    # )

    # 누가 작성했는지 (User 연결)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,  # 작성자 삭제되면 이 노트도 같이 삭제됨
        related_name="study_notes",  # user.study_notes 이런 식으로 접근 가능
    )

    # 노트 기본 내용
    title = models.CharField(max_length=255)  # 노트 제목 (최대 255자)
    content = models.TextField()  # 실제 학습 내용 작성하는 부분
    ai_summary = models.TextField()  # AI가 요약해주는 내용 (필수값)

    class Meta:
        db_table = "study_notes"  # DB 테이블 이름 지정 (ERD랑 맞춤)
        ordering = ["-created_at"]  # 최신순으로 정렬해서 조회됨

    def __str__(self):
        # 그룹 연결되면 아래 주석 해제해서 그룹 이름도 같이 보이게 만들면 됨
        # return f"[{self.study_group.name}] {self.title} by {self.author}"
        return f"{self.title} by {self.author}"  # 지금은 제목+작성자만 표시


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

    def __str__(self):
        return f"Image for Note {self.study_note.id}"


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

    def __str__(self):
        # 어드민 페이지에서 보기 편하게 표시
        return f"Attachment for Note {self.study_note.id}"
