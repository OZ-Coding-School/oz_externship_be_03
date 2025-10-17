from django.db import models

from apps.core.models import BaseModel

from .recruitments import Recruitment


class RecruitmentAttachment(BaseModel):
    recruitment = models.ForeignKey(Recruitment, on_delete=models.CASCADE, related_name="attachments")  # 공고
    file_url = models.CharField(max_length=255, unique=True)  # 파일 URL
    file_name = models.CharField(max_length=50)  # 파일명

    def __str__(self) -> str:
        return self.file_name


class RecruitmentImage(BaseModel):
    recruitment = models.ForeignKey(Recruitment, on_delete=models.CASCADE, related_name="images")  # 공고
    img_url = models.CharField(max_length=255, unique=True)  # 이미지 URL

    def __str__(self) -> str:
        return f"{self.recruitment.title} 이미지"
