from typing import cast
from uuid import UUID

# from asgiref.sync import async_to_sync # Removed import
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chat.pagination import ChatMessagePagination
from apps.chat.permissions import IsGroupMember
from apps.chat.serializers import (
    ChatMessageSerializer,
    ChatRoomSerializer,
    TotalUnreadMessageCountSerializer,
)
from apps.chat.services.chat_service import ChatRoomService
from apps.core.views import ExceptionHandledAPIView
from apps.studies.models.groups import GroupMember
from apps.users.models import User


class TotalUnreadMessageCountView(ExceptionHandledAPIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Chat"],
        summary="전체 안 읽은 메시지 수 총합 API",
        description="로그인한 사용자의 모든 채팅방에 대한 전체 안 읽은 메시지 수를 조회합니다.",
        responses={
            status.HTTP_200_OK: inline_serializer(
                name="TotalUnreadMessageCountResponse",
                fields={"total_unread_count": serializers.IntegerField()},
            ),
        },
    )
    def get(self, request: Request) -> Response:
        user = cast(User, request.user)
        total_unread_count: int = ChatRoomService.get_total_unread_message_count(user)
        serializer = TotalUnreadMessageCountSerializer({"total_unread_count": total_unread_count})
        return Response(serializer.data, status=status.HTTP_200_OK)


class ChatMessageListView(APIView):
    serializer_class = ChatMessageSerializer
    permission_classes = [IsAuthenticated, IsGroupMember]
    pagination_class = ChatMessagePagination

    @extend_schema(
        tags=["Chat"],
        summary="메시지 목록 조회 API",
        description="""
        특정 그룹의 메시지 목록을 페이지네이션으로 조회합니다.
        로그인한 사용자는 해당 스터디 그룹의 멤버여야 합니다.
        """,
        parameters=[
            OpenApiParameter(
                name="study_group_uuid",
                type=str,
                location=OpenApiParameter.PATH,
                description="그룹 UUID",
                required=True,
            ),
            OpenApiParameter(
                name="page",
                type=int,
                location=OpenApiParameter.QUERY,
                description="페이지 번호 (기본값 1)",
                required=False,
            ),
            OpenApiParameter(
                name="page_size",
                type=int,
                location=OpenApiParameter.QUERY,
                description="페이지당 개수 (기본값 20)",
                required=False,
            ),
        ],
        responses={
            status.HTTP_200_OK: ChatMessageSerializer,
            status.HTTP_403_FORBIDDEN: {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "example": "해당 사용자는 스터디 그룹 멤버가 아닙니다."},
                },
            },
        },
    )
    def get(self, request: Request, study_group_uuid: UUID) -> Response:
        queryset = ChatRoomService.get_chatroom_messages(study_group_uuid)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        serializer = self.serializer_class(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class ChatRoomListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Chat"],
        summary="채팅방 목록 조회 API",
        description="사용자가 속한 모든 채팅방의 목록과 각 방의 마지막 메시지, 안 읽은 메시지 수를 조회합니다.",
        responses=ChatRoomSerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        user = cast(User, request.user)

        chat_rooms_data = list(ChatRoomService.get_chat_rooms_for_user(user))
        serializer = ChatRoomSerializer(chat_rooms_data, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
