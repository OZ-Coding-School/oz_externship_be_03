from typing import Any, Dict, Iterable

from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Count, OuterRef, Subquery
from django.db.models.functions import Coalesce

from apps.chat.models import ChatMessage, LastReadMessage
from apps.studies.models.groups import StudyGroup
from apps.users.models import User


class ChatRoomService:
    @staticmethod
    def get_chat_rooms_for_user(user: User) -> Iterable[Dict[str, Any]]:
        # 사용자가 속한 스터디 그룹 목록 조회
        study_groups = StudyGroup.objects.filter(members__user=user)

        # 각 그룹의 마지막 메시지 서브쿼리
        last_message_subquery = (
            ChatMessage.objects.filter(study_group_id=OuterRef("pk"))
            .order_by("-created_at")
            .values(
                "content",
                "sender__nickname",
                "created_at",
            )[:1]
        )

        # 사용자의 마지막 읽은 메시지 ID 서브쿼리 (존재하지 않을 경우를 대비)
        last_read_message_id_subquery = LastReadMessage.objects.filter(study_group_id=OuterRef("pk"), user=user).values(
            "message_id"
        )

        # 안 읽은 메시지 수 계산 서브쿼리
        unread_count_subquery = (
            ChatMessage.objects.filter(
                study_group_id=OuterRef("pk"),
                id__gt=Coalesce(Subquery(last_read_message_id_subquery), 0),
            )
            .values("study_group_id")
            .annotate(count=Count("id"))
            .values("count")
        )

        # 스터디 그룹 정보와 함께 마지막 메시지, 안 읽은 메시지 수 조합
        chat_rooms = study_groups.annotate(
            last_message_content=Subquery(last_message_subquery.values("content")),
            last_message_sender_nickname=Subquery(last_message_subquery.values("sender__nickname")),
            last_message_created_at=Subquery(last_message_subquery.values("created_at")),
            unread_count=Coalesce(Subquery(unread_count_subquery, output_field=models.IntegerField()), 0),
        ).values(
            "id",
            "name",
            "last_message_content",
            "last_message_sender_nickname",
            "last_message_created_at",
            "unread_count",
        )

        return chat_rooms
