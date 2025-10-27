from django.db import models

from apps.core.models import BaseModel


class RecruitmentTag(BaseModel):
    """공고-태그 연결 테이블"""

    # 문자열 참조 사용 → 순환 참조 완전 차단
    recruitment = models.ForeignKey(
        "recruitments.Recruitment",
        on_delete=models.CASCADE,
        related_name="recruitment_tags",
    )
    tag = models.ForeignKey(
        "recruitments.Tag",
        on_delete=models.CASCADE,
        related_name="recruitment_tags",
    )

    class Meta:
        db_table = "recruitments_recruitment_tag"
        verbose_name = "공고 태그 연결"
        verbose_name_plural = "공고 태그 연결 목록"
        constraints = [
            models.UniqueConstraint(
                fields=["recruitment", "tag"],
                name="unique_recruitment_tag",
            )
        ]

    def __str__(self) -> str:
        """관리자 페이지나 shell에서 보기 쉽게"""
        return f"{self.recruitment.title} - {self.tag.name}"
