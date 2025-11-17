from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import CheckConstraint, Q

from apps.core.models import UUIDBaseModel
from apps.studies.models.groups import GroupMember


class GroupSchedule(UUIDBaseModel):
    if TYPE_CHECKING:
        id: int

    study_group = models.ForeignKey(
        "StudyGroup",
        on_delete=models.CASCADE,
        related_name="schedules",
        help_text="해당 일정이 속한 스터디 그룹",
    )
    title = models.CharField(max_length=255, null=False, default="", help_text="스터디 일정 제목 (필수)")
    objective = models.CharField(max_length=255, null=False, default="", help_text="스터디 목표 (필수)")
    session_date = models.DateField(null=False, help_text="스터디 진행일 (YYYY-MM-DD)")
    start_time = models.TimeField(null=False, help_text="스터디 시작 시간 (HH:MM)")
    end_time = models.TimeField(null=False, help_text="스터디 종료 시간 (HH:MM)")

    participants = models.ManyToManyField(
        GroupMember,
        through="studies.ScheduleParticipant",
        related_name="study_schedules",
    )

    class Meta:
        db_table = "group_schedules"
        app_label = "studies"
        # 최신순 정렬이 기본 -> but. created_at이 극악의 확률로 겹칠 것을 대비해서 id 필드를 내림차순 정렬로 secondary ordering 으로 추가.
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["study_group", "session_date"], name="idx_by_group_date"),
            models.Index(fields=["session_date", "-created_at"], name="idx_by_date_created_desc"),
        ]
        constraints = [
            CheckConstraint(
                check=Q(end_time__gt=models.F("start_time")),
                name="valid_schedule_time_range",
            ),
        ]

    def clean(self) -> None:
        if self.start_time >= self.end_time:
            raise ValidationError("스터디 종료 시간은 시작 시간보다 늦어야 합니다.")

    def __str__(self) -> str:
        return f"StudySchedule(id={self.id}, group={self.study_group.id}, title={self.title})"


class ScheduleParticipant(models.Model):
    pk = models.CompositePrimaryKey("schedule_id", "member_id")

    schedule = models.ForeignKey(
        "GroupSchedule",
        on_delete=models.CASCADE,
        related_name="schedule_participants",
        null=False,
        blank=False,
        help_text="어떤 스케줄에 속하는지 (FK)",
    )
    member = models.ForeignKey(
        "GroupMember",
        on_delete=models.CASCADE,
        related_name="schedule_participants",
        null=False,
        blank=False,
        help_text="스케줄에 참가하는 그룹 멤버 (FK)",
    )

    class Meta:
        db_table = "schedule_participants"
        app_label = "studies"
        indexes = [
            models.Index(fields=["schedule"], name="idx_by_schedule"),
            models.Index(fields=["member"], name="idx_by_member"),
        ]

    def __str__(self) -> str:
        return (
            f"ScheduleParticipant(schedule={self.schedule.id}, member={self.member.id}, leader={self.member.is_leader})"
        )
