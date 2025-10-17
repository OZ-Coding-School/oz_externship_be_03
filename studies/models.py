from django.conf import settings
from django.db import models

from apps.core.models import BaseModel  # 생성·수정 시간 자동 포함


class StudyGroup(BaseModel):
    # 스터디 그룹 이름
    name = models.CharField(max_length=50)
    # 제목만 있는 그룹도 있을 수 있어서 소개는 선택
    description = models.TextField(blank=True, null=True)
    # 생성/수정 시간은 BaseModel에서 자동으로 기록됨

    def __str__(self):
        # 관리자나 디버깅용으로 이름만 표시
        return self.name


class StudyNote(BaseModel):
    # 어느 그룹 노트인지 연결, 그룹 삭제되면 같이 삭제
    group = models.ForeignKey(StudyGroup, on_delete=models.CASCADE, related_name="notes")
    # 작성자, 유저 삭제되면 해당 노트도 삭제됨
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="study_notes")
    # 노트 제목 (리스트나 검색용)
    title = models.CharField(max_length=50)
    # 노트 본문 (길이 제한 없음)
    content = models.TextField()
    # 요약은 선택사항 (비워도 됨)
    summary = models.TextField(blank=True, null=True)

    class Meta:
        # 최신 작성 순으로 정렬
        ordering = ["-created_at"]

    def __str__(self):
        # 보기 쉽게 그룹명, 제목, 작성자 표시
        return f"[{self.group.name}] {self.title} by {self.author}"
