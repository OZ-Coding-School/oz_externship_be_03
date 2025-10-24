from typing import TYPE_CHECKING
from django.conf import settings
from django.db import models
from apps.core.models import BaseModel

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser as User
    from apps.studies.models.groups import StudyGroup
    from datetime import datetime

    id: int
    study_group: "StudyGroup"
    study_group_id: int
    created_at: "datetime"
    updated_at: "datetime"


class StudySchedule(BaseModel):


    study_group = models.ForeignKey(
        "studies.StudyGroup",
        on_delete=models.CASCADE,
        related_name="schedules",
        help_text="해당 일정이 속한 스터디 그룹",
    )
    title = models.CharField(
        max_length=100,
        null=False,
        help_text="스터디 일정 제목 (필수)"
    )
    objective = models.CharField(
        max_length=255,
        null=False,
        help_text="스터디 목표 (필수)"
    )
    session_date = models.DateField(
        null=False,
        help_text="스터디 진행일 (YYYY-MM-DD)"
    )
    start_time = models.TimeField(
        null=False,
        help_text="스터디 시작 시간 (HH:MM)"
    )
    end_time = models.TimeField(
        null=False,
        help_text="스터디 종료 시간 (HH:MM)"
    )

    class Meta:
        db_table = "group_schedules"
        ordering = ["session_date", "start_time", "created_at"]
        verbose_name = "스터디 그룹 일정"
        verbose_name_plural = "스터디 그룹 일정 목록"
        indexes = [
            models.Index(fields=["study_group", "session_date"], name="ix_group_schedules_group_date"),
            models.Index(fields=["session_date", "-created_at"], name="ix_group_schedules_date_created_desc"),
        ]

    def __str__(self) -> str:
        return f"StudySchedule(id={self.id}, group={self.study_group_id}, title={self.title})"


class ScheduleParticipant(BaseModel):


    schedule = models.ForeignKey(
        StudySchedule,
        on_delete=models.CASCADE,
        related_name="participants",
        help_text="어떤 스케줄에 속하는지 (FK)"
    )
    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="schedule_participations",
        help_text="스터디 그룹 멤버 (FK)"
    )
    is_leader = models.BooleanField(
        default=False,
        help_text="리더 여부"
    )

    class Meta:
        db_table = "schedule_participants"
        constraints = [
            models.UniqueConstraint(
                fields=["schedule", "member"],
                name="uq_schedule_participants_schedule_member",
            )
        ]
        indexes = [
            models.Index(fields=["schedule"], name="ix_schedule_participants_schedule"),
            models.Index(fields=["member"], name="ix_schedule_participants_member"),
        ]
        verbose_name = "스케줄 참여자"
        verbose_name_plural = "스케줄 참여자 목록"

    def __str__(self) -> str:
        return f"ScheduleParticipant(schedule={self.schedule_id}, member={self.member_id}, leader={self.is_leader})"
