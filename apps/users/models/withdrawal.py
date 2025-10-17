# 임시 모델
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


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

    class Reason(models.TextChoices):
        NO_LONGER_NEEDED    = "NO_LONGER_NEEDED", "서비스 이용할 시간이 없음"
        LACK_OF_INTEREST    = "LACK_OF_INTEREST", "관심이 사라짐"
        TOO_DIFFICULT       = "TOO_DIFFICULT", "서비스를 이용하기가 너무 어려움"
        FOUND_BETTER_SERVICE= "FOUND_BETTER_SERVICE", "더 좋은 대안을 찾음"
        PRIVACY_CONCERNS    = "PRIVACY_CONCERNS", "개인정보/보안 우려"
        POOR_SERVICE_QUALITY= "POOR_SERVICE_QUALITY", "서비스 품질 불만"
        TECHNICAL_ISSUES    = "TECHNICAL_ISSUES", "기술적 문제(버그 등)"
        LACK_OF_CONTENT     = "LACK_OF_CONTENT", "원하는 콘텐츠나 기능의 부족"
        OTHER               = "OTHER", "기타"

    id = models.BigAutoField(primary_key=True)

    # FK: users(id), NULL 허용 + on_delete=SET_NULL (스펙: delete : set null)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_index=True,
        related_name="withdrawals",
        verbose_name="사용자",
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
        verbose_name = "회원 탈퇴"
        verbose_name_plural = "회원 탈퇴 목록"

    def __str__(self) -> str:
        user_part = getattr(self.user, "email", None) or "(탈퇴/없음)"
        return f"[Withdrawal #{self.pk}] {user_part} - {self.get_reason_display()}"
