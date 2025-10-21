from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chat.serializers.chat_serializers import (
    ChatMessageCreateRequestSerializer,
    ChatMessageResponseSerializer,
)


class ChatMessageCreateAPIView(APIView):
    @extend_schema(
        tags=["Chat"],
        summary="메시지 전송 API",
        description="""
        특정 스터디 그룹에 채팅 메시지를 전송합니다.
        인증된 사용자만 메시지를 전송할 수 있으며, 요청 본문으로 메시지 내용을 받습니다.
        """,
        request=ChatMessageCreateRequestSerializer,
        responses={
            201: ChatMessageResponseSerializer,
            403: {
                "description": "스터디 그룹 멤버가 아님",
                "example": {
                    "status": "error",
                    "code": "NOT_A_MEMBER",
                    "message": "해당 사용자는 스터디 그룹 멤버가 아닙니다.",
                    "data": None,
                },
            },
        },
        parameters=[
            OpenApiParameter(
                name="study_group_id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description="그룹 ID",
                required=True,
            ),
        ],
    )
    def post(self, request: Request, study_group_id: int) -> Response:  # Add type hints
        # Spec API 단계에서는 비즈니스 로직을 구현하지 않습니다.
        # 여기서는 단순히 시리얼라이저를 통한 요청 유효성 검사 및 응답 구조만 보여줍니다.
        request_serializer = ChatMessageCreateRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)

        # 임시 응답 데이터 (실제 로직은 기능 구현 단계에서 추가)
        response_data = {
            "message_id": 1,  # 임시 ID
            "sender_id": request.user.id if request.user.is_authenticated else 0,  # 임시 sender_id
            "study_group_id": study_group_id,
            "content": request_serializer.validated_data["content"],
            "file_url": None,
            "created_at": "2025-10-15T10:30:00Z",  # 임시 시간
        }
        response_serializer = ChatMessageResponseSerializer(response_data)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
