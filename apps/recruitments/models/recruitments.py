import uuid
from datetime import datetime, timedelta

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel
from apps.studies.models.groups import StudyGroup


# 기본 마감일: 생성일 + 14일
def default_close_at() -> datetime:
    return timezone.now() + timedelta(days=14)


class Recruitment(BaseModel):
    """스터디 모집 공고"""

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    study_group = models.ForeignKey(StudyGroup, on_delete=models.CASCADE, related_name="recruitments", null=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recruitments")
    title = models.CharField(max_length=50)
    content = models.TextField()
    estimated_fee = models.IntegerField()
    expected_headcount = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    views_count = models.PositiveIntegerField(default=0)
    close_at = models.DateTimeField(default=default_close_at)
    is_closed = models.BooleanField(default=False)

    #  피드백 반영: Tag 관계 추가 (문자열 참조로 순환참조 방지)
    tags = models.ManyToManyField(
        "recruitments.Tag",  # 문자열 참조
        through="recruitments.RecruitmentTag",  # 문자열 참조
        related_name="recruitments",
        blank=True,
    )

    def __str__(self) -> str:
        return self.title
