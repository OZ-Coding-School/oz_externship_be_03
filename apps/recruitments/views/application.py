
from typing import Any, Optional, cast
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from apps.recruitments.models import Application
from apps.recruitments.serializers.application import (
    ApplicationCreateSerializer,
    ApplicationDetailSerializer,
    MyApplicationListSerializer,
    MyApplicationDetailSerializer,
)
from apps.users.models import User

# 사용자용 지원서 API (작성, 조회, 취소)
class ApplicationListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        # 내가 작성한 모든 지원서 목록 조회
        user: User = cast(User, request.user)
        applications = Application.objects.filter(user=user)
        serializer = MyApplicationListSerializer(applications, many=True)
        return Response(serializer.data)

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        # 지원서 작성
        serializer = ApplicationCreateSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            application = serializer.save()
            return Response(ApplicationDetailSerializer(application).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ApplicationWithdrawAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request: Request, pk: int, *args: Any, **kwargs: Any) -> Response:
        # 지원서 취소
        user: User = cast(User, request.user)
        application = get_object_or_404(Application, pk=pk, user=user)

        if application.status in ["APPROVED", "REJECTED"]:
            return Response({"detail": "이미 처리된 지원서는 취소할 수 없습니다."}, status=status.HTTP_400_BAD_REQUEST)

        application.status = "WITHDRAWN"
        application.save()
        serializer = ApplicationDetailSerializer(application)
        return Response(serializer.data)


class MyApplicationListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        # 내 지원서 목록 (상태 필터링 가능)
        user: User = cast(User, request.user)
        status_filter: Optional[str] = request.query_params.get("status")
        applications = Application.objects.filter(user=user)
        if status_filter:
            applications = applications.filter(status=status_filter)
        serializer = MyApplicationListSerializer(applications, many=True)
        return Response(serializer.data)


class MyApplicationDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, pk: int, *args: Any, **kwargs: Any) -> Response:
        # 내 지원서 상세 조회
        user: User = cast(User, request.user)
        application: Application = get_object_or_404(Application, pk=pk, user=user)
        serializer = MyApplicationDetailSerializer(application)
        return Response(serializer.data)