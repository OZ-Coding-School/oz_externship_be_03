from django.db import models
import uuid
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User

# ----------------------------
# 기본 마감일 함수
# ----------------------------
def default_close_at():
    return timezone.now() + timedelta(days=14)

# ----------------------------
# 스터디 그룹
# ----------------------------
class StudyGroup(models.Model):
    name = models.CharField(max_length=50, unique=True)  # 그룹명
    description = models.TextField(blank=True, null=True)  # 그룹 설명
    created_at = models.DateTimeField(auto_now_add=True)  # 생성일시
    updated_at = models.DateTimeField(null=True, blank=True)  # 수정일시

# ----------------------------
# 태그 (사용자 정의 태그)
# ----------------------------
class Tag(models.Model):
    name = models.CharField(max_length=20, unique=True)  # 태그명
    created_at = models.DateTimeField(auto_now_add=True)  # 생성일시
    updated_at = models.DateTimeField(null=True, blank=True)  # 수정일시

# ----------------------------
# 스터디 구인 공고
# ----------------------------
class Recruitment(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)  # 외부 노출용 UUID
    study_group = models.ForeignKey(
        StudyGroup, on_delete=models.CASCADE, related_name="recruitments"
    )  # 소속 스터디 그룹
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="recruitments"
    )  # 공고 작성자
    title = models.CharField(max_length=50)  # 공고 제목
    content = models.TextField()  # 공고 내용
    estimated_fee = models.IntegerField()  # 예상 강의 결제 비용
    expected_headcount = models.PositiveSmallIntegerField()  # 예상 모집 인원
    views_count = models.IntegerField(default=0)  # 조회수
    close_at = models.DateTimeField(default=default_close_at)  # 공고 마감일
    is_closed = models.BooleanField(default=False)  # 공고 마감 상태
    created_at = models.DateTimeField(auto_now_add=True)  # 생성일시
    updated_at = models.DateTimeField(null=True, blank=True)  # 수정일시

# ----------------------------
# 스터디 구인 공고 ↔ 태그 중간 테이블
# ----------------------------
class RecruitmentTag(models.Model):
    recruitment = models.ForeignKey(
        Recruitment, on_delete=models.CASCADE, related_name="tags"
    )  # 공고
    tag = models.ForeignKey(
        Tag, on_delete=models.CASCADE, related_name="recruitments"
    )  # 태그
    created_at = models.DateTimeField(auto_now_add=True)  # 생성일시
    updated_at = models.DateTimeField(null=True, blank=True)  # 수정일시

    class Meta:
        unique_together = ("recruitment", "tag")  # 공고-태그 조합 유니크

# ----------------------------
# 공고 첨부 파일
# ----------------------------
class RecruitmentAttachment(models.Model):
    recruitment = models.ForeignKey(
        Recruitment, on_delete=models.CASCADE, related_name="attachments"
    )  # 공고
    file_url = models.CharField(max_length=255, unique=True)  # 파일 URL
    file_name = models.CharField(max_length=50)  # 원본 파일명
    created_at = models.DateTimeField(auto_now_add=True)  # 생성일시
    updated_at = models.DateTimeField(null=True, blank=True)  # 수정일시

# ----------------------------
# 공고 이미지
# ----------------------------
class RecruitmentImage(models.Model):
    recruitment = models.ForeignKey(
        Recruitment, on_delete=models.CASCADE, related_name="images"
    )  # 공고
    img_url = models.CharField(max_length=255)  # 이미지 URL
    created_at = models.DateTimeField(auto_now_add=True)  # 생성일시
    updated_at = models.DateTimeField(null=True, blank=True)  # 수정일시

# ----------------------------
# 공고 북마크
# ----------------------------
class RecruitmentBookmark(models.Model):
    recruitment = models.ForeignKey(
        Recruitment, on_delete=models.CASCADE, related_name="bookmarks"
    )  # 공고
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="recruitment_bookmarks"
    )  # 북마크한 유저
    created_at = models.DateTimeField(auto_now_add=True)  # 생성일시
    updated_at = models.DateTimeField(null=True, blank=True)  # 수정일시

    class Meta:
        unique_together = ("user", "recruitment")  # 유저-공고 조합 유니크
