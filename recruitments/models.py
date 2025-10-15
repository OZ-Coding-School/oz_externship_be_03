import uuid
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


# ----------------------------
# 기본 마감일 함수
# ----------------------------
def default_close_at():
    return timezone.now() + timedelta(days=14)


# ----------------------------
# 스터디 그룹
# ----------------------------
class StudyGroup(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True)


# ----------------------------
# 태그 (사용자 정의 태그)
# ----------------------------
class Tag(models.Model):
    name = models.CharField(max_length=20, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True)


# ----------------------------
# 스터디 구인 공고
# ----------------------------
class Recruitment(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    study_group = models.ForeignKey(
        StudyGroup, on_delete=models.CASCADE, related_name="recruitments"
    )
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="recruitments"
    )
    title = models.CharField(max_length=50)
    content = models.TextField()
    estimated_fee = models.IntegerField()
    expected_headcount = models.PositiveSmallIntegerField()
    views_count = models.IntegerField(default=0)
    close_at = models.DateTimeField(default=default_close_at)
    is_closed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True)


# ----------------------------
# 스터디 구인 공고 ↔ 태그 중간 테이블
# ----------------------------
class RecruitmentTag(models.Model):
    recruitment = models.ForeignKey(
        Recruitment, on_delete=models.CASCADE, related_name="tags"
    )
    tag = models.ForeignKey(
        Tag, on_delete=models.CASCADE, related_name="recruitments"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["recruitment", "tag"], name="unique_recruitment_tag"
            )
        ]


# ----------------------------
# 공고 첨부 파일
# ----------------------------
class RecruitmentAttachment(models.Model):
    recruitment = models.ForeignKey(
        Recruitment, on_delete=models.CASCADE, related_name="attachments"
    )
    file_url = models.CharField(max_length=255, unique=True)
    file_name = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True)


# ----------------------------
# 공고 이미지
# ----------------------------
class RecruitmentImage(models.Model):
    recruitment = models.ForeignKey(
        Recruitment, on_delete=models.CASCADE, related_name="images"
    )
    img_url = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True)


# ----------------------------
# 공고 북마크
# ----------------------------
class RecruitmentBookmark(models.Model):
    recruitment = models.ForeignKey(
        Recruitment, on_delete=models.CASCADE, related_name="bookmarks"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="recruitment_bookmarks"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "recruitment"], name="unique_user_bookmark"
            )
        ]
