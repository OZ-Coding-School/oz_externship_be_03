from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from ...core.models import BaseModel


# 스터디 그룹 상태 Enum
class StudyGroupStatus(models.TextChoices):
    PENDING = "PENDING", "대기중"
    ONGOING = "ONGOING", "진행중"
    ENDED = "ENDED", "종료됨"


# 스터디 그룹
class StudyGroup(BaseModel):
    name = models.CharField(max_length=20, null=False, default="")
    introduction = models.CharField(max_length=500, null=True, blank=True)
    max_headcount = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        null=False,
        default=2,
    )
    profile_img_url = models.CharField(max_length=255, null=True, blank=True)
    start_at = models.DateTimeField(null=False)
    end_at = models.DateTimeField(null=False)
    status = models.CharField(
        max_length=10,
        choices=StudyGroupStatus.choices,
        default=StudyGroupStatus.PENDING,
        null=False,
    )

    class Meta:
        db_table = "study_groups"
        app_label = "studies"  # mypy와 migration 모두 안전하게 하기 위해 추가

    def __str__(self) -> str:
        return self.name


# 스터디 강의 (중간 테이블)
class StudyLecture(BaseModel):
    lecture_id = models.BigIntegerField(null=False, default=0)
    study_group = models.ForeignKey("StudyGroup", on_delete=models.CASCADE, related_name="lectures", null=False)

    class Meta:
        db_table = "study_lectures"
        unique_together = ("lecture_id", "study_group")
        app_label = "studies"


# 그룹 멤버
class GroupMember(BaseModel):
    study_group = models.ForeignKey("StudyGroup", on_delete=models.CASCADE, related_name="members", null=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="group_members", null=False
    )
    is_leader = models.BooleanField(default=False, null=False)

    class Meta:
        db_table = "group_members"
        unique_together = ("study_group", "user_id")
        app_label = "studies"


# 그룹 스케줄
class GroupSchedule(BaseModel):
    study_group = models.ForeignKey("StudyGroup", on_delete=models.CASCADE, related_name="schedules", null=False)
    title = models.CharField(max_length=255, null=False, default="")
    objective = models.CharField(max_length=255, null=False, default="")
    session_date = models.DateField(null=False)
    start_time = models.TimeField(null=False)
    end_time = models.TimeField(null=False)

    class Meta:
        db_table = "group_schedules"
        app_label = "studies"


# 스케줄 참여자
class ScheduleParticipant(BaseModel):
    schedule = models.ForeignKey("GroupSchedule", on_delete=models.CASCADE, related_name="participants", null=False)
    member = models.ForeignKey("GroupMember", on_delete=models.CASCADE, related_name="schedules", null=False)

    class Meta:
        db_table = "schedule_participants"
        unique_together = ("schedule", "member")
        app_label = "studies"
