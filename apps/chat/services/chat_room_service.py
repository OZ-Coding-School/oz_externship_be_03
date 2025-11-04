from typing import Any, Dict, Iterable

from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Count, ExpressionWrapper, F, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce

from apps.chat.models import ChatMessage, LastReadMessage
from apps.studies.models.groups import GroupMember, StudyGroup
from apps.users.models import User


class ChatRoomService:
    @staticmethod
    def get_chat_rooms_for_user(user: User) -> Iterable[Dict[str, Any]]:
        # 사용자가 속한 스터디 그룹 목록 조회
        member_study_group_ids = GroupMember.objects.filter(user=user).values("study_group")
        study_groups = StudyGroup.objects.filter(id__in=Subquery(member_study_group_ids))

        # 각 그룹의 마지막 메시지 서브쿼리
        last_message = ChatMessage.objects.filter(study_group=OuterRef("pk")).order_by("-created_at")

        # 마지막으로 읽은 메시지 ID를 그룹에 annotate. 없으면 0으로.
        groups_with_last_read = study_groups.annotate(
            last_read_id=Coalesce(
                Subquery(
                    LastReadMessage.objects.filter(study_group=OuterRef("pk"), user=user).values("message_id")[:1]
                ),
                Value(0),
                output_field=models.IntegerField(),
            )
        )

        # 최종적으로 필요한 값들을 annotate
        chat_rooms = groups_with_last_read.annotate(
            last_message_content=Subquery(last_message.values("content")[:1]),
            last_message_sender_nickname=Subquery(last_message.values("sender__nickname")[:1]),
            last_message_created_at=Subquery(last_message.values("created_at")[:1]),
            unread_count=Coalesce(
                Subquery(
                    ChatMessage.objects.filter(study_group=OuterRef("pk"), id__gt=OuterRef("last_read_id"))
                    .values("study_group")
                    .annotate(count=Count("id"))
                    .values("count"),
                    output_field=models.IntegerField(),
                ),
                Value(0),
            ),
        ).values(
            "id",
            "name",
            "last_message_content",
            "last_message_sender_nickname",
            "last_message_created_at",
            "unread_count",
        )

        return chat_rooms
