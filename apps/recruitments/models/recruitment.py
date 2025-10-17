import uuid
from datetime import datetime, timedelta
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from apps.core.models import BaseModel
from .studygroup import StudyGroup


# 기본 마감일: 생성일 + 14일
def default_close_at() -> datetime:
    return timezone.now() + timedelta(days=14)


class Recruitment(BaseModel):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)  # 고유 ID
    study_group = models.ForeignKey(StudyGroup, on_delete=models.CASCADE, related_name="recruitments")  # 스터디
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recruitments"
    )  # 작성자
    title = models.CharField(max_length=50)  # 제목
    content = models.TextField()  # 내용
    estimated_fee = models.IntegerField()  # 예상 회비
    expected_headcount = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10)]
    )  # 모집 인원
    views_count = models.PositiveIntegerField(default=0)  # 조회수
    close_at = models.DateTimeField(default=default_close_at)  # 마감일
    is_closed = models.BooleanField(default=False)  # 마감 여부

    def __str__(self) -> str:
        return self.title
