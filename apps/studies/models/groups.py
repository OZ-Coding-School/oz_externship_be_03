from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import CheckConstraint, Q

from ...core.models import BaseModel


class StudyGroupStatus(models.TextChoices):
    PENDING = "PENDING", "대기중"
    ONGOING = "ONGOING", "진행중"
    ENDED = "ENDED", "종료됨"


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
        app_label = "studies"

    def __str__(self) -> str:
        return self.name


class StudyLecture(BaseModel):
    pk = models.CompositePrimaryKey("lecture_id", "study_group_id")

    lecture = models.ForeignKey(
        "lecture.CrawledLecture",
        on_delete=models.CASCADE,
        related_name="study_links",
    )
    study_group = models.ForeignKey(
        "StudyGroup",
        on_delete=models.CASCADE,
        related_name="lectures",
    )

    class Meta:
        db_table = "study_lectures"
        app_label = "studies"


class GroupMember(BaseModel):
    study_group = models.ForeignKey(
        "StudyGroup",
        on_delete=models.CASCADE,
        related_name="members",
        null=False,
        blank=False,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="group_members",
        null=False,
        blank=False,
    )
    is_leader = models.BooleanField(default=False, null=False)

    class Meta:
        db_table = "group_members"
        app_label = "studies"
        constraints = [
            models.UniqueConstraint(
                fields=["study_group", "user"],
                name="uq_group_member",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user.id} in group {self.study_group.id}"