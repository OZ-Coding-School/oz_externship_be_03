from __future__ import annotations

from typing import Any, Dict

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from apps.core.exceptions import Conflict
from apps.recruitments.models.application import Application
from apps.recruitments.models.recruitments import Recruitment
from apps.users.models import User


def create_application(
    *,
    recruitment_uuid: str,
    user: User,
    payload: Dict[str, Any],
) -> Application:
    """
    공고 지원 서비스
    - 공고 존재/마감 여부 검증
    - 본인 공고 지원 금지
    """
    # 1) 공고 조회 (uuid 기준)
    try:
        recruitment = Recruitment.objects.get(uuid=recruitment_uuid)
    except Recruitment.DoesNotExist:
        raise NotFound({"error": "해당 스터디를 찾을 수 없습니다."})

    now = timezone.now()

    # 2) 마감/종료 여부 검사
    if recruitment.is_closed or recruitment.close_at <= now:
        raise ValidationError({"error": "모집이 마감된 스터디입니다."})

    # 3) 본인 공고 지원 금지
    if recruitment.author_id == getattr(user, "id", None):
        raise ValidationError({"error": "본인이 작성한 공고에는 지원할 수 없습니다."})

    # 4) 지원 생성 (중복 지원은 DB 제약으로 막힘)
    try:
        with transaction.atomic():
            app = Application.objects.create(
                recruitment=recruitment,
                user=user,
                self_introduction=payload["self_introduction"],
                motivation=payload["motivation"],
                objective=payload["objective"],
                available_time=payload["available_time"],
                has_study_experience=payload["has_study_experience"],
                study_experience=payload.get("study_experience", ""),
            )
    except IntegrityError:
        # UniqueConstraint: (recruitment, user) 중복
        raise Conflict({"error": "이미 지원한 스터디입니다."})

    return app
