from __future__ import annotations

from typing import Any, Mapping, Sequence

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.authentication import BaseAuthentication
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.utils.exception_handler import exception_handler as handle_api_exception
from apps.users.models.user import User
from apps.users.serializers.user_info_serializers import (
    DupNicknameQuerySerializer,
    DupNicknameResponseSerializer,
)
from apps.users.views.responses import ok


class UserDupNicknameView(APIView):
    """
    닉네임 중복 확인 API
    """

    permission_classes = [AllowAny]
    authentication_classes: tuple[type[BaseAuthentication], ...] = ()

    @extend_schema(
        tags=["Users"],
        summary="닉네임 중복 확인",
        description="쿼리 파라미터로 전달된 'nickname'의 중복 여부 반환",
        request=None,
        responses={200: DupNicknameResponseSerializer},
        parameters=[
            OpenApiParameter(
                name="nickname",
                location=OpenApiParameter.QUERY,
                required=False,
                type=OpenApiTypes.STR,
                description="중복 여부를 확인할 닉네임",
            ),
            OpenApiParameter(
                name="case_insensitive",
                location=OpenApiParameter.QUERY,
                required=False,
                type=OpenApiTypes.BOOL,
                description="대소문자 구분 여부, 구분안함=true (기본: true)",
            ),
        ],
    )
    def get(self, request: Request) -> Response:
        serializer = DupNicknameQuerySerializer(data=request.query_params)

        try:
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            return handle_api_exception(e, {"view": self, "request": request})

        nickname = serializer.validated_data["nickname"]
        case_insensitive = serializer.validated_data["case_insensitive"]

        filters_ = {"nickname__iexact": nickname} if case_insensitive else {"nickname": nickname}
        is_dup = User.objects.filter(**filters_).exists()

        return ok(
            "이미 사용중인 닉네임입니다." if is_dup else "사용 가능한 닉네임입니다.",
            data={"nickname": nickname, "available": not is_dup},
            status_code=status.HTTP_200_OK,
        )
