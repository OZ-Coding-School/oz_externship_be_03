from django.contrib.auth import get_user_model
from django.db import models

from apps.core.models import BaseModel

User = get_user_model()


class Notification(BaseModel):

    class NotificationType(models.TextChoices):
        APPLICATION_CREATED = "APPLICATIONS_CREATED", "공고 지원 알림"
        APPLICATION_STATUS_APPROVAL = "APPLICATION_STATUS_APPROVAL", "지원 승인 알림"
        APPLICATION_STATUS_REJECTION = "APPLICATION_STATUS_REJECTION", "지원 거절 알림"
        STUDY_MEMBER_JOINED = "STUDY_MEMBER_JOINED", "스터디 그룹 신규 참여 알림"
        STUDY_REVIEW_REQUEST = "STUDY_REVIEW_REQUEST", "스터디 후기 작성 요청 알림"
        STUDY_SCHEDULE_UPCOMING = "STUDY_SCHEDULE_UPCOMING", "예정 스케줄 알림"
        STUDY_SCHEDULE_TODAY = "STUDY_SCHEDULE_TODAY", "금일 스케줄 알림"
        STUDY_RECORD_CREATED = "STUDY_RECORD_CREATED", "스터디 기록 작성 알림"
        SYSTEM = "SYSTEM", "시스템 알림"
        CUSTOM = "CUSTOM", "기타 사용자 정의 알림"

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="유저",
    )
    content = models.CharField(max_length=300, verbose_name="알림 내용,")
    type = models.CharField(
        max_length=300,
        choices=NotificationType,
        verbose_name="알림 종류",
    )
    is_read = models.BooleanField(
        default=False,
        verbose_name="읽음 여부",
    )
    back_url_link = models.CharField(
        max_length=300,
        blank=True,
        null=True,
        verbose_name="이동 URL",
    )

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self) -> str:
        return f"{self.content}"
