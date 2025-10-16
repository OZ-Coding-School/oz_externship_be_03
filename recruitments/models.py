import uuid
from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


# 공통 타임스탬프
class TimeStamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class StudyGroup(TimeStamped):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)  # 그룹 설명

    def __str__(self) -> str:
        return self.name


class Tag(TimeStamped):
    name = models.CharField(max_length=20, unique=True)  # 태그명

    def __str__(self) -> str:
        return self.name


# mypy 오류 수정: 반환 타입을 datetime으로 지정
def default_close_at() -> datetime:
    return timezone.now() + timedelta(days=14)


class Recruitment(TimeStamped):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    study_group = models.ForeignKey(StudyGroup, on_delete=models.CASCADE, related_name="recruitments")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="recruitments")
    title = models.CharField(max_length=50)
    content = models.TextField()
    estimated_fee = models.IntegerField()  # 예상 회비
    expected_headcount = models.PositiveSmallIntegerField()  # 모집 인원
    views_count = models.PositiveIntegerField(default=0)  # 조회수
    close_at = models.DateTimeField(default=default_close_at)  # 마감일
    is_closed = models.BooleanField(default=False)  # 마감 여부

    def __str__(self) -> str:
        return self.title


class RecruitmentTag(TimeStamped):
    recruitment = models.ForeignKey(Recruitment, on_delete=models.CASCADE, related_name="tags")
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name="recruitments")

    class Meta:
        unique_together = ("recruitment", "tag")  # 중복 방지


class RecruitmentAttachment(TimeStamped):
    recruitment = models.ForeignKey(Recruitment, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to="recruitments/files/")  # 첨부 파일
    file_name = models.CharField(max_length=50)

    def __str__(self) -> str:
        return self.file_name


class RecruitmentImage(TimeStamped):
    recruitment = models.ForeignKey(Recruitment, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="recruitments/images/")  # 공고 이미지

    def __str__(self) -> str:
        return f"{self.recruitment.title} 이미지"


class RecruitmentBookmark(TimeStamped):
    recruitment = models.ForeignKey(Recruitment, on_delete=models.CASCADE, related_name="bookmarks")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="recruitment_bookmarks")

    class Meta:
        unique_together = ("user", "recruitment")  # 한 번만 북마크 가능

    def __str__(self) -> str:
        return f"{self.user.username} 북마크 {self.recruitment.title}"
