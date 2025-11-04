from typing import Any, List, cast

from django.contrib.auth import get_user_model
from django.db.models.query import QuerySet
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chat.models import ChatMessage
from apps.chat.pagination import ChatMessagePagination
from apps.chat.serializers import ChatMessageSerializer, ChatRoomSerializer
from apps.chat.services.chat_room_service import ChatRoomService
from apps.studies.models.groups import GroupMember
from apps.users.models import User


class ChatMessageListView(ListAPIView[ChatMessage]):
    serializer_class = ChatMessageSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ChatMessagePagination

    def get_queryset(self) -> QuerySet[ChatMessage]:
        study_group_id = self.kwargs["study_group_id"]
        return ChatMessage.objects.filter(study_group_id=study_group_id).order_by("-created_at")

    @extend_schema(
        tags=["Chat"],
        summary="메시지 목록 조회 API",
        description="""
        특정 그룹의 메시지 목록을 페이지네이션으로 조회합니다.
        로그인한 사용자는 해당 스터디 그룹의 멤버여야 합니다.
        """,
        parameters=[
            OpenApiParameter(
                name="study_group_id",
                type=int,
                location=OpenApiParameter.PATH,
                description="그룹 ID",
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
            status.HTTP_200_OK: {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "example": "success"},
                    "code": {"type": "string", "example": "SUCCESS"},
                    "message": {"type": "string", "example": "메시지 목록 조회 성공"},
                    "data": {
                        "type": "object",
                        "properties": {
                            "messages": {
                                "type": "array",
                                "items": ChatMessageSerializer,
                            },
                            "pagination": {
                                "type": "object",
                                "properties": {
                                    "page": {"type": "integer"},
                                    "page_size": {"type": "integer"},
                                    "total_count": {"type": "integer"},
                                },
                            },
                        },
                    },
                },
            },
            status.HTTP_403_FORBIDDEN: {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "example": "error"},
                    "code": {"type": "string", "example": "NOT_A_MEMBER"},
                    "message": {"type": "string", "example": "해당 사용자는 스터디 그룹 멤버가 아닙니다."},
                    "data": {"type": "string", "nullable": True, "example": None},
                },
            },
        },
    )
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        study_group_id = self.kwargs["study_group_id"]
        user = request.user
        assert user.is_authenticated

        # 사용자가 스터디 그룹의 멤버인지 확인
        if not GroupMember.objects.filter(study_group_id=study_group_id, user=user).exists():
            return Response(
                {
                    "status": "error",
                    "code": "NOT_A_MEMBER",
                    "message": "해당 사용자는 스터디 그룹 멤버가 아닙니다.",
                    "data": None,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


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
