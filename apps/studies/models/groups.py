import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


# 스터디 그룹 상태 Enum
class StudyGroupStatus(models.TextChoices):
    PENDING = "PENDING", "대기중"
    ONGOING = "ONGOING", "진행중"
    ENDED = "ENDED", "종료됨"


# 스터디 그룹
class StudyGroup(models.Model):
    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(max_length=20)
    introduction = models.CharField(max_length=500, null=True, blank=True)
    max_headcount = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    profile_img_url = models.URLField(null=True, blank=True)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    status = models.CharField(
        max_length=10,
        choices=StudyGroupStatus.choices,
        default=StudyGroupStatus.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = "study_groups"

    def __str__(self) -> str:
        return self.name


# 스터디 강의 (중간 테이블)
class StudyLecture(models.Model):
    lecture_id = models.BigIntegerField()
    study_group = models.ForeignKey("StudyGroup", on_delete=models.CASCADE, related_name="lectures")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = "study_lectures"
        unique_together = ("lecture_id", "study_group")


# 그룹 멤버
class GroupMember(models.Model):
    id = models.BigAutoField(primary_key=True)
    study_group = models.ForeignKey("StudyGroup", on_delete=models.CASCADE, related_name="members")
    user_id = models.BigIntegerField()
    is_leader = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = "group_members"
        unique_together = ("study_group", "user_id")


# 그룹 스케줄
class GroupSchedule(models.Model):
    id = models.BigAutoField(primary_key=True)
    study_group = models.ForeignKey("StudyGroup", on_delete=models.CASCADE, related_name="schedules")
    title = models.CharField(max_length=255)
    objective = models.CharField(max_length=255)
    session_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = "group_schedules"


# 스케줄 참여자
class ScheduleParticipant(models.Model):
    schedule = models.ForeignKey("GroupSchedule", on_delete=models.CASCADE, related_name="participants")
    member = models.ForeignKey("GroupMember", on_delete=models.CASCADE, related_name="schedules")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = "schedule_participants"
        unique_together = ("schedule", "member")
