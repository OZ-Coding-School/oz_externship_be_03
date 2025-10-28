# mypy 타입 체킹을 위한 임포트
from typing import TYPE_CHECKING

from django.db import transaction

# 다른 앱의 모델은 순환 참조를 방지하기 위해 TYPE_CHECKING 블록 안에서 임포트합니다.
if TYPE_CHECKING:
    from apps.users.models.user import User

    from apps.studies.models.groups import StudyGroup

from .models import ChatMessage


class ChatMessageService:
    @staticmethod
    @transaction.atomic
    def create_chat_message(
        *,
        sender: "User",
        study_group: "StudyGroup",
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
    async def edit_chat_message(
        message: ChatMessage, new_content: str
    ) -> ChatMessage:
        """
        채팅 메시지 내용을 수정하고 업데이트된 메시지를 반환합니다.
        """
        message.content = new_content
        await message.asave()
        return message
