from django.db import models

from apps.core.models import BaseModel
from apps.recruitments.models.recruitments import Recruitment


class RecruitmentImage(BaseModel):
    recruitment = models.ForeignKey(Recruitment, on_delete=models.CASCADE, related_name="images")
    img_url = models.URLField(max_length=500)

    class Meta:
        db_table = "recruitment_images"
        verbose_name = "공고 이미지"
        verbose_name_plural = "공고 이미지 목록"
