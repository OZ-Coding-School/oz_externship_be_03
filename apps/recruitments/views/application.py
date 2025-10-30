from typing import Any

from django.contrib.auth.models import AbstractUser
from drf_spectacular.utils import extend_schema
from django.contrib.auth.models import AnonymousUser
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView

from apps.recruitments.models.application import Application, ApplicationStatus
from apps.recruitments.serializers.application import ApplicationSerializer
from apps.recruitments.models.application import Application
from apps.recruitments.serializers.application import (
    ApplicationSerializer,
    ApplicationStatusUpdateSerializer,
)


class ApplicationListCreateAPIView(ListCreateAPIView[Application]):
    queryset: QuerySet[Application] = Application.objects.all()
class ApplicationAPIView(APIView):
    serializer_class = ApplicationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self) -> QuerySet[Application]:
        user = self.request.user
        if isinstance(user, AnonymousUser):
            return Application.objects.none()
        return Application.objects.filter(user=user)
    @extend_schema(tags=["Applications"], summary="지원서 작성/등록")
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer: BaseSerializer[Application]) -> None:
        user = self.request.user if not isinstance(self.request.user, AnonymousUser) else None
        recruitment = serializer.validated_data["recruitment"]
        if Application.objects.filter(recruitment=recruitment, user=user).exists():
            raise ValidationError("이미 해당 공고에 지원하셨습니다.")
        serializer.save(user=user)
    @extend_schema(
        tags=["Applications"], summary="내 지원 내역 조회", responses={200: ApplicationSerializer(many=True)}
    )
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = request.user if request.user.is_authenticated else None
        applications = Application.objects.filter(user=user)
        serializer = self.serializer_class(instance=applications, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ApplicationWithdrawAPIView(APIView):
    def post(self, request: Any, pk: int) -> Response:
        application = get_object_or_404(Application, pk=pk)
        if application.user != request.user:
            raise PermissionDenied("본인의 지원서만 취소할 수 있습니다.")
        application.status = ApplicationStatus.WITHDRAWN
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
        return Response({"detail": "지원이 취소되었습니다."}, status=status.HTTP_200_OK)
        out = ApplicationSerializer(instance=application)
        return Response(out.data, status=status.HTTP_200_OK)
