from django.db import models
from django.db.models import UniqueConstraint

from apps.users.enums import Provider

from ...core.models import BaseModel
from .managers import SocialUserManager


class SocialUser(BaseModel):
    """
    Social User 모델
    """

    user = models.ForeignKey("users.user", on_delete=models.CASCADE, null=False, related_name="socials")

    provider = models.CharField(max_length=20, choices=Provider.choices, help_text="소셜 로그인 제공 업체", null=False)

    provider_id = models.CharField(max_length=255, help_text="소셜로그인 제공 업체에서 주는 고유 id", null=False)

    objects = SocialUserManager()

    class Meta:
        db_table = "social_users"
        # PK 자동 고유 인덱스 생성
        constraints = [
            # 한 유저가 같은 provider를 중복 연결하는 것 방지
            UniqueConstraint(
                fields=["user", "provider"],
                name="uq_user_provider_one",
            ),
            # 동일 provider에 중복 provider 방지
            UniqueConstraint(fields=["provider", "provider_id"], name="uq_provider_uid"),
        ]

    def __str__(self) -> str:
        return f"{self.provider} - {self.user.email}"
