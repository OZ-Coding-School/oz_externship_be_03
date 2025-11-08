from uuid import UUID

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.db.models import Count, IntegerField, OuterRef, QuerySet, Subquery, Value
from django.db.models.functions import Coalesce

from apps.chat.models import ChatMessage, LastReadMessage
from apps.studies.models.groups import StudyGroup
from apps.users.models import User


class ChatRoomService:
    @staticmethod
    def get_chat_rooms_for_user(user: User) -> QuerySet[StudyGroup]:
        # 사용자가 속한 스터디 그룹 목록 조회
        last_message_subquery = ChatMessage.objects.filter(study_group_id=OuterRef("pk")).order_by("-created_at")
        last_read_message_subquery = LastReadMessage.objects.filter(
            study_group_id=OuterRef("study_group_id"), user=user
        )
        total_message_subquery = (
            ChatMessage.objects.filter(study_group_id=OuterRef("pk"))
            .values("study_group_id")
            .annotate(count=Count("id"))
            .values("count")[:1]
        )
        chat_rooms = (
            StudyGroup.objects.filter(group_members__user=user)
            .only("id", "name")
            .annotate(
                last_message_id=Subquery(last_message_subquery.values("id")[:1]),
                last_message_content=Subquery(last_message_subquery.values("content")[:1]),
                last_message_created_at=Subquery(last_message_subquery.values("created_at")[:1]),
                last_message_sender_nickname=Subquery(last_message_subquery.values("sender__nickname")[:1]),
                unread_message_count=Coalesce(
                    Subquery(
                        ChatMessage.objects.filter(
                            study_group_id=OuterRef("pk"),
                            id__gt=Coalesce(Subquery(last_read_message_subquery.values("message_id")[:1]), Value(0)),
                        )
                        .values("study_group_id")
                        .annotate(count=Count("id"))
                        .values("count")[:1],
                        output_field=IntegerField(),
                    ),
                    Value(0),
                ),
            )
        )

        return chat_rooms

    @staticmethod
    def get_chatroom_messages(study_group_uuid: UUID) -> QuerySet[ChatMessage]:
        """
        특정 스터디 그룹의 채팅 메시지를 조회합니다.
        """
        return ChatMessage.objects.filter(study_group__uuid=study_group_uuid).order_by("created_at")

    @staticmethod
    @transaction.atomic
    def create_chat_message(
        sender: User,
        study_group: StudyGroup,
        content: str,
    ) -> ChatMessage:
        """
        채팅 메시지를 생성하고 관련 비즈니스 로직을 처리합니다.
        """
        chat_message = ChatMessage.objects.create(
            sender=sender,
            study_group=study_group,
            content=content,
        )
        # TODO: 메시지 생성 후 관련 로직 추가 (예: 웹소켓으로 브로드캐스트)
        return chat_message

    @staticmethod
    def broadcast_member_removal(study_group_id: int, user_id: int, user_nickname: str, is_kick: bool) -> None:
        """
        스터디 멤버가 제거되었음을 실시간으로 브로드캐스트합니다.
        - 제거된 사용자에게는 강제 접속 종료 메시지를 보냅니다.
        - 다른 멤버들에게는 시스템 메시지를 보냅니다.
        """
        channel_layer = get_channel_layer()
        room_group_name = f"chat_{study_group_id}"

        # 1. 제거된 사용자에게 강제 접속 종료 메시지 전송
        async_to_sync(channel_layer.group_send)(
            f"user_{user_id}",
            {
                "type": "force_disconnect",
                "study_group_id": study_group_id,
            },
        )

        # 2. 채팅방의 다른 멤버들에게 시스템 메시지 전송
        if is_kick:
            message = f"{user_nickname}님이 리더에 의해 스터디에서 제외되었습니다."
        else:
            message = f"{user_nickname}님이 스터디를 떠났습니다."

        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                "type": "system_message",
                "message": message,
            },
        )
