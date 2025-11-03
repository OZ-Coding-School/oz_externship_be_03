from __future__ import annotations

import uuid

from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.studies.models.schedules import GroupSchedule
from apps.studies.serializers.schedules import GroupScheduleCreateSerializer


class GroupScheduleCreateView(APIView):
    """
    스터디 그룹 일정 생성 (REQ-SCHD-001, REQ-SCHD-002)
    """

    permission_classes = (permissions.IsAuthenticated,)

    @extend_schema(
        operation_id="CreateGroupSchedule",
        request=GroupScheduleCreateSerializer,
        responses={
            201: OpenApiResponse(description="스케줄이 생성되었습니다."),
            401: OpenApiResponse(description="인증 필요"),
            403: OpenApiResponse(description="권한 없음"),
            404: OpenApiResponse(description="스터디 그룹을 찾을 수 없음"),
            409: OpenApiResponse(description="중복 스케줄 또는 무결성 충돌"),
        },
        tags=["StudyGroupSchedule"],
        summary="스터디 스케줄 생성",
        description=(
            "입력 항목:\n"
            "• study_group: 해당 스케줄 그룹의 uuid 값\n"
            "• title: 스케줄 명\n"
            "• objective: 스터디 목표\n"
            "• session_date: 진행일\n"
            "• start_time: 시작 시간\n"
            "• end_time: 종료 시간\n"
            "• participants: 참여자 선택 (선택적)\n"
        ),
        examples=[
            OpenApiExample(
                "create Schedule",
                value={
                    "study_group": uuid.uuid4(),
                    "title": "주간 알고리즘 스터디",
                    "objective": "그리디 알고리즘 실습",
                    "session_date": "2025-10-28",
                    "start_time": "14:00:00",
                    "end_time": "16:00:00",
                },
                request_only=True,
            )
        ],
    )
    def post(self, request: Request) -> Response:
        serializer = GroupScheduleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # 중복 스케줄 방지 (동일 그룹 + 날짜 + 시간대)
        exists = GroupSchedule.objects.filter(
            study_group=serializer.validated_data["study_group"],
            session_date=serializer.validated_data["session_date"],
            start_time=serializer.validated_data["start_time"],
        ).exists()

        if exists:
            return Response({"detail": "같은 시간대에 이미 스케줄이 존재합니다."}, status=409)

        serializer.save()
        return Response(serializer.data, status=201)
