from __future__ import annotations

from typing import Sequence

from celery import shared_task  # type: ignore[import-untyped]
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.users.models import Withdrawal

User = get_user_model()


@shared_task  # type: ignore[misc]
def delete_withdrawn_users(*, batch_size: int = 1000, dry_run: bool = False) -> int:
    """
    due_date < today 이고 user_id가 남아있는 탈퇴 건을 대상으로
    해당 User만 물리 삭제. Withdrawal은 FK(on_delete=SET_NULL) 덕에 user_id=NULL로 남음.

    반환: 처리된 사용자 수
    """
    today = timezone.localdate()
    processed_total = 0

    while True:
        # 매 사이클마다 새로 스냅샷: 이미 처리된 건은 user_id가 NULL이 되어 자동 제외됨
        user_ids: Sequence[int] = list(
            Withdrawal.objects.filter(due_date__lt=today, user_id__isnull=False)
            .values_list("user_id", flat=True)
            .distinct()[:batch_size]
        )
        if not user_ids:
            break

        if dry_run:
            # 점검 모드: 실제 삭제 없이 개수만 집계
            processed_total += len(user_ids)
            # 루프 종료(드라이런은 1배치만 샘플링)
            break

        with transaction.atomic():
            # User 삭제
            User.objects.filter(id__in=user_ids).delete()
            processed_total += len(user_ids)

    return processed_total
