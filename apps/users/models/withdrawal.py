# 임시 모델
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel
from apps.users.enums import Reason


class Withdrawal(BaseModel):
    """
    회원 탈퇴 정보 저장 테이블 (withdrawals)
    - id: BIGINT PK (자동증분)
    - user: FK -> users(id), ON DELETE SET NULL (NULL 허용)
    - reason: ENUM(텍스트 choices)
    - reason_detail: VARCHAR(500) NOT NULL
    - due_date: DATE NOT NULL (계정 물리 삭제 예정일)
    - created_at: DATETIME NOT NULL (생성 시각)
    - updated_at: DATETIME NULL (수정 시각, 없을 수도 있음)
    """

    # FK: users(id), NULL 허용 + on_delete=SET_NULL
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="withdrawals",
    )

    reason = models.CharField(
        "탈퇴 사유",
        max_length=50,
        choices=Reason.choices,
        null=False,
        blank=False,
    )

    reason_detail = models.CharField(
        "구체적인 탈퇴 사유",
        max_length=500,
        null=False,
        blank=False,
    )

    # 계정 삭제 예정일: DATE 타입
    due_date = models.DateField(
        "계정 삭제 예정일",
        null=False,
        blank=False,
    )

    class Meta:
        db_table = "withdrawals"

    def reason_label(self) -> str:
        return str(dict(Reason.choices).get(self.reason, self.reason))

    def __str__(self) -> str:
        user_part = getattr(self.user, "email", None) or "(탈퇴/없음)"
        return f"{self.pk}] {user_part} - {self.reason_label()}"
