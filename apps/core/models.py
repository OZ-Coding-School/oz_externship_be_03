import uuid
from typing import ClassVar

from django.db import models
from django.db.models.query import QuerySet
from django.utils import timezone


class SoftDeleteManager(models.Manager["TimeStampModel"]):
    """소프트 삭제된 객체를 제외하고 조회하는 매니저"""

    def get_queryset(self) -> QuerySet["TimeStampModel"]:
        """deleted_at이 NULL인 객체만 필터링합니다."""
        return super().get_queryset().filter(deleted_at__isnull=True)


class TimeStampModel(models.Model):
    """생성/수정일시, 소프트 삭제 기능이 포함된 기본 추상 모델"""

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="생성일시")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="수정일시")
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True, verbose_name="삭제일시")

    objects: ClassVar[SoftDeleteManager] = SoftDeleteManager()
    all_objects: ClassVar[models.Manager["TimeStampModel"]] = models.Manager()

    class Meta:
        abstract = True

    def delete(self, using: str | None = None, keep_parents: bool = False) -> None:
        """실제 삭제 대신 deleted_at에 현재 시간을 기록합니다."""
        self.deleted_at = timezone.now()
        self.save()

    def restore(self) -> None:
        """삭제된 객체를 복구합니다."""
        self.deleted_at = None
        self.save()


class UUIDTimeStampModel(TimeStampModel):
    """외부 노출용 UUID 필드가 포함된 타임스탬프 모델"""

    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        db_index=True,
        unique=True,
        verbose_name="고유식별자(UUID)",
    )

    class Meta:
        abstract = True
