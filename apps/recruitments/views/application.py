from typing import Any

from django.contrib.auth.models import AbstractUser
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.recruitments.models.application import Application
from apps.recruitments.serializers.application import (
    ApplicationSerializer,
    ApplicationStatusUpdateSerializer,
)


class ApplicationAPIView(APIView):
    serializer_class = ApplicationSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Applications"], summary="지원서 작성/등록")
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=["Applications"], summary="내 지원 내역 조회", responses={200: ApplicationSerializer(many=True)}
    )
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = request.user if request.user.is_authenticated else None
        applications = Application.objects.filter(user=user)
        serializer = self.serializer_class(instance=applications, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ApplicationStatusUpdateAPIView(APIView):
    serializer_class = ApplicationStatusUpdateSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Applications"], summary="지원서 상태 변경 (지원/승인/거절/취소)")
    def patch(self, request: Request, application_id: int, *args: Any, **kwargs: Any) -> Response:
        user = request.user if request.user.is_authenticated else None
        application = Application.objects.get(id=application_id, user=user)
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        application.status = serializer.validated_data["status"]
        application.save()
        out = ApplicationSerializer(instance=application)
        return Response(out.data, status=status.HTTP_200_OK)
