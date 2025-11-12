from __future__ import annotations

from typing import Any, cast

from django.db import transaction
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.core.views import ExceptionHandledAPIView
from apps.recruitments.serializers.application_serializers import (
    ApplicationResponseSerializer,
)
from apps.recruitments.services.application_withdrawal_services import (
    withdraw_application,
)
from apps.users.models import User


class ApplicationWithdrawAPIView(ExceptionHandledAPIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Applications"],
        summary="지원 취소",
        description="특정 지원을 취소합니다. 이미 승인/거절/취소된 항목은 취소할 수 없습니다.",
        responses=inline_serializer(
            name="ApplicationCreateResponse",
            fields={
                "detail": serializers.CharField(),
                "data": ApplicationResponseSerializer(),
            },
        ),
    )
    @transaction.atomic
    def patch(self, request: Request, application_uuid: str, *args: Any, **kwargs: Any) -> Response:
        result = withdraw_application(user=cast(User, request.user), application_uuid=application_uuid)

        response_serializer = ApplicationResponseSerializer(result).data
        return Response(
            {
                "detail": "스터디에 성공적으로 지원했습니다.",
                "data": response_serializer,
            },
            status=status.HTTP_200_OK,
        )
