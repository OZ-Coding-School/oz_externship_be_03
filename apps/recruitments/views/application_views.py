from __future__ import annotations

from typing import Any, cast

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import permissions, serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.recruitments.serializers.application_serializers import (
    ApplicationCreateSerializer,
    ApplicationResponseSerializer,
)
from apps.recruitments.services.application_services import create_application
from apps.users.models import User


class ApplicationCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Applications"],
        summary="스터디 공고 지원",
        description="로그인한 사용자가 스터디 공고에 지원 합니다.",
        request=ApplicationCreateSerializer,
        responses=inline_serializer(
            name="ApplicationCreateResponse",
            fields={
                "detail": serializers.CharField(),
                "data": ApplicationResponseSerializer(),
            },
        ),
    )
    def post(self, request: Request, recruitment_uuid: str, *args: Any, **kwargs: Any) -> Response:
        request_serializer = ApplicationCreateSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)

        app = create_application(
            recruitment_uuid=recruitment_uuid,
            user=cast(User, request.user),
            payload=request_serializer.validated_data,
        )
        response_serializer = ApplicationResponseSerializer(app).data

        return Response(
            {
                "detail": "스터디에 성공적으로 지원했습니다.",
                "data": response_serializer,
            },
            status=status.HTTP_201_CREATED,
        )
