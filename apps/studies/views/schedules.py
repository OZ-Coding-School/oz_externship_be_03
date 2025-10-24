from __future__ import annotations

from typing import Any
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.studies.models.groups import StudyGroup
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
            422: OpenApiResponse(description="검증 실패(필드/비즈니스 규칙 오류)"),
        },
        tags=["StudyGroupSchedule"],
        summary="스터디 스케줄 생성",
        description=(
            "경로의 group_id를 사용해 해당 스터디 그룹에 스케줄을 생성합니다.\n\n"
            "입력 항목:\n"
            "• 스케줄 명 (title)\n"
            "• 스터디 목표 (objective)\n"
            "• 진행일 (session_date)\n"
            "• 시작 시간 (start_time)\n"
            "• 종료 시간 (end_time)\n"
            "• 참여자 선택 (participants - 선택적)\n"
        ),
        examples=[
            OpenApiExample(
                "create Schedule",
                value={
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
    def post(self, request: Request, group_id: int, *args: Any, **kwargs: Any) -> Response:
        study_group = get_object_or_404(StudyGroup, id=group_id)

        user_id = getattr(request.user, "pk", None)
        if user_id is None:
            return Response(status=401)

        # 중복 스케줄 방지 (동일 그룹 + 날짜 + 시간대)
        exists = GroupSchedule.objects.filter(
            study_group=study_group,
            session_date=request.data.get("session_date"),
            start_time=request.data.get("start_time"),
        ).exists()
        if exists:
            return Response({"detail": "같은 시간대에 이미 스케줄이 존재합니다."}, status=409)

        data = {"study_group": study_group.pk, **request.data}
        serializer = GroupScheduleCreateSerializer(data=data, context={"request": request})

        if not serializer.is_valid():
            return Response(serializer.errors, status=422)

        try:
            serializer.save()
        except IntegrityError:
            return Response({"detail": "스케줄 생성 중 무결성 충돌이 발생했습니다."}, status=409)

        return Response(serializer.data, status=201)
