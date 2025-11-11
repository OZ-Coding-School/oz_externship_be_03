
from typing import Any, Optional, cast

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from apps.recruitments.models import Application
from apps.recruitments.serializers.admin_application import (
    AdminApplicationListSerializer,
    AdminApplicationDetailSerializer,
)
from apps.studies.models.groups import GroupMember
from apps.users.models import User

# 관리자용 지원서 목록/상세/상태변경 API
@extend_schema(
    tags=["Admin Application"],  # Swagger 그룹명
    summary="지원 내역 목록 조회 (관리자)",
    description="관리자가 본인이 작성한 모집 공고에 대한 전체 지원 내역을 조회합니다.",
    parameters=[
        OpenApiParameter(name="q", description="검색 키워드 (공고명, 닉네임, 이메일)", required=False, type=str),
        OpenApiParameter(name="status", description="지원 상태 필터링", required=False, type=str),
        OpenApiParameter(name="limit", description="조회 개수", required=False, type=int),
        OpenApiParameter(name="offset", description="페이지 시작 위치", required=False, type=int),
        OpenApiParameter(name="order", description="정렬 순서 (asc 또는 desc)", required=False, type=str),
    ],
    responses={200: AdminApplicationListSerializer(many=True)}
)

class AdminRecruitmentApplicationListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        # 현재 로그인한 유저가 작성한 모집 공고에 대한 지원서만 조회
        user: User = cast(User, request.user)
        applications = Application.objects.filter(recruitment__author=user)
        serializer = AdminApplicationListSerializer(applications, many=True)
        return Response(serializer.data)


@extend_schema(
    tags=["Admin Application"],
    summary="지원 내역 상세 조회 (관리자)",
    description="관리자가 특정 지원서의 상세 정보를 조회합니다.",
    responses={
        200: AdminApplicationDetailSerializer,
        403: OpenApiResponse(description="관리자 권한 없음"),
        404: OpenApiResponse(description="지원서가 존재하지 않음"),
    }
)
class AdminApplicationDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, pk: int, *args: Any, **kwargs: Any) -> Response:
        # 지원서 존재 여부 확인
        application = get_object_or_404(Application, pk=pk)

        # 본인이 작성한 공고의 지원서인지 확인
        if application.recruitment.author != request.user:
            return Response({"detail": "권한이 없습니다."}, status=status.HTTP_403_FORBIDDEN)

        serializer = AdminApplicationDetailSerializer(application)
        return Response(serializer.data)


@extend_schema(
    tags=["Admin Application"],
    summary="지원 상태 변경 (승인/거절)",
    description="관리자가 지원서를 승인하거나 거절합니다.",
    request={
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["APPROVED", "REJECTED"],
                "description": "변경할 상태값"
            }
        },
        "required": ["status"]
    },
    responses={
        200: OpenApiResponse(description="상태 변경 성공", response={
            "application_id": 123,
            "status": "APPROVED",
            "updated_at": "2025-11-10T23:30:00Z"
        }),
        400: OpenApiResponse(description="잘못된 요청 또는 정원 초과"),
        403: OpenApiResponse(description="권한 없음"),
        404: OpenApiResponse(description="지원서 없음"),
    }
)
class AdminApplicationStatusUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request: Request, pk: int, *args: Any, **kwargs: Any) -> Response:
        application = get_object_or_404(Application, pk=pk)

        # 작성자 권한 확인
        if application.recruitment.author != request.user:
            return Response({"detail": "권한이 없습니다."}, status=status.HTTP_403_FORBIDDEN)

        # 이미 처리된 지원서인지 확인
        if application.status != "APPLIED":
            return Response({"detail": "이미 처리된 지원서입니다."}, status=status.HTTP_400_BAD_REQUEST)

        # 상태값 유효성 검사
        new_status: Optional[str] = request.data.get("status")
        if new_status not in ["APPROVED", "REJECTED"]:
            return Response({"detail": "잘못된 상태값입니다."}, status=status.HTTP_400_BAD_REQUEST)

        # 승인 시 그룹 정원 체크 및 멤버 등록
        study_group = application.recruitment.study_group
        if new_status == "APPROVED":
            if study_group is None:
                return Response({"detail": "스터디 그룹이 존재하지 않습니다."}, status=status.HTTP_400_BAD_REQUEST)
            if study_group.group_members.count() >= application.recruitment.expected_headcount:
                return Response({"detail": "모집 인원이 초과되었습니다."}, status=status.HTTP_400_BAD_REQUEST)
            GroupMember.objects.create(user=application.user, study_group=study_group)

        # 상태 업데이트
        application.status = new_status
        application.save()

        return Response({
            "application_id": application.id,
            "status": application.status,
            "updated_at": application.updated_at
        }, status=status.HTTP_200_OK)