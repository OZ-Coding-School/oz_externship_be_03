from django.db import models

from apps.core.models import BaseModel

from .recruitments import Recruitment
from .tag import Tag


class RecruitmentTag(BaseModel):
    pk = models.CompositePrimaryKey("recruitment_id", "tag_id")
    recruitment = models.ForeignKey(Recruitment, on_delete=models.CASCADE, related_name="tags")  # 공고
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name="recruitments")  # 태그

    class Meta:
        constraints = [models.UniqueConstraint(fields=["recruitment", "tag"], name="unique_recruitment_tag")]  # 중복 방
