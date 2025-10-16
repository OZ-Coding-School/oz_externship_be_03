import uuid

from django.db import models

from apps.core.models import BaseModel


class StudyGroup(BaseModel):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, blank=True)  # 최소 필드(임시)

    class Meta:
        db_table = "study_groups"
