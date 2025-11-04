from typing import Any

from django.contrib.auth.models import AnonymousUser
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.generics import ListCreateAPIView
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView

from apps.recruitments.models.application import Application, ApplicationStatus
from apps.recruitments.serializers.application import ApplicationSerializer


class ApplicationListCreateAPIView(ListCreateAPIView[Application]):
    queryset: QuerySet[Application] = Application.objects.all()
    serializer_class = ApplicationSerializer

    def get_queryset(self) -> QuerySet[Application]:
        user = self.request.user
        if isinstance(user, AnonymousUser):
            return Application.objects.none()
        return Application.objects.filter(user=user)

    def perform_create(self, serializer: BaseSerializer[Application]) -> None:
        user = self.request.user if not isinstance(self.request.user, AnonymousUser) else None
        recruitment = serializer.validated_data["recruitment"]
        if Application.objects.filter(recruitment=recruitment, user=user).exists():
            raise ValidationError("이미 해당 공고에 지원하셨습니다.")
        serializer.save(user=user)


class ApplicationWithdrawAPIView(APIView):
    def post(self, request: Any, pk: int) -> Response:
        application = get_object_or_404(Application, pk=pk)
        if application.user != request.user:
            raise PermissionDenied("본인의 지원서만 취소할 수 있습니다.")
        application.status = ApplicationStatus.WITHDRAWN
        application.save()
        return Response({"detail": "지원이 취소되었습니다."}, status=status.HTTP_200_OK)
