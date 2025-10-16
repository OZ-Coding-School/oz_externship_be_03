import uuid
from datetime import datetime, timedelta

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

# 공통 타임스탬프 모델 import
from apps.core.models import BaseModel


class StudyGroup(BaseModel):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)  # 스터디 그룹 소개

    def __str__(self):
        return self.name


class Tag(BaseModel):
    name = models.CharField(max_length=20, unique=True)  # 사용자 정의 태그명

    def __str__(self):
        return self.name


# 기본 마감일: 생성 시점 + 14일
def default_close_at() -> datetime:
    return timezone.now() + timedelta(days=14)


class Recruitment(BaseModel):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    study_group = models.ForeignKey(StudyGroup, on_delete=models.CASCADE, related_name="recruitments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recruitments")
    title = models.CharField(max_length=50)
    content = models.TextField()
    estimated_fee = models.IntegerField()  # 예상 회비
    expected_headcount = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10)]
    )  # 모집 인원 1~10 제한
    views_count = models.PositiveIntegerField(default=0)
    close_at = models.DateTimeField(default=default_close_at)
    is_closed = models.BooleanField(default=False)

    def __str__(self):
        return self.title


class RecruitmentTag(BaseModel):
    recruitment = models.ForeignKey(Recruitment, on_delete=models.CASCADE, related_name="tags")
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name="recruitments")

    class Meta:
        unique_together = ("recruitment", "tag")


class RecruitmentAttachment(BaseModel):
    recruitment = models.ForeignKey(Recruitment, on_delete=models.CASCADE, related_name="attachments")
    file_url = models.CharField(max_length=255)  # ERD 기준 URL
    file_name = models.CharField(max_length=50)

    def __str__(self):
        return self.file_name


class RecruitmentImage(BaseModel):
    recruitment = models.ForeignKey(Recruitment, on_delete=models.CASCADE, related_name="images")
    image_url = models.CharField(max_length=255)  # ERD 기준 URL

    def __str__(self):
        return f"{self.recruitment.title} 이미지"


class RecruitmentBookmark(BaseModel):
    recruitment = models.ForeignKey(Recruitment, on_delete=models.CASCADE, related_name="bookmarks")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recruitment_bookmarks",
    )

    class Meta:
        unique_together = ("user", "recruitment")

    def __str__(self):
        return f"{self.user.username} 북마크 {self.recruitment.title}"
