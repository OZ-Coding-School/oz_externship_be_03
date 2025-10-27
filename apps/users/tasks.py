from __future__ import annotations

from typing import List

from celery import shared_task  # type: ignore[import-untyped]
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.users.models import Withdrawal

User = get_user_model()


@shared_task  # type: ignore[misc]
def delete_withdrawn_users(*, batch_size: int = 1000) -> int:
    """
    due_date < today 이고 user_id가 남아있는 탈퇴 건을 대상으로
    해당 User만 물리 삭제. Withdrawal은 FK(on_delete=SET_NULL) 덕에 user_id=NULL로 남음.

    반환: 처리된 사용자 수
    """
    today = timezone.localdate()

    # 1) 스냅샷: 삭제 전, 대상 user_id를 고정 리스트로 확보
    user_ids: List[int] = list(
        Withdrawal.objects.filter(due_date__lte=today, user_id__isnull=False)
        .values_list("user_id", flat=True)
        .distinct()
        .order_by("user_id")
    )
    total = len(user_ids)

    # 삭제 대상이 없을 경우 즉시 종료
    if total == 0:
        return 0

    # 2) 슬라이싱 + 배치별 트랜잭션
    processed_total = 0

    for start in range(0, total, batch_size):
        chunk = user_ids[start : start + batch_size]
        if not chunk:
            break
        with transaction.atomic():
            deleted, _ = User.objects.filter(id__in=chunk).delete()
            # delete()는 (삭제된 총 행 수, per-model 분포 dict) 반환
        processed_total += len(chunk)

    return processed_total
