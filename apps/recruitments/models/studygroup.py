from django.db import models
from apps.core.models import BaseModel


class StudyGroup(BaseModel):
    name = models.CharField(max_length=20, unique=True)  # 스터디 이름
    introduction = models.TextField(blank=True)  # 소개

    def __str__(self) -> str:
        return self.name
