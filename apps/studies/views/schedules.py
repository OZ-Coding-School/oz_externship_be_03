from __future__ import annotations

import uuid

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import permissions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.studies.models.groups import StudyGroup
from apps.studies.models.schedules import GroupSchedule
from apps.studies.serializers.schedules import (
    GroupScheduleCreateSerializer,
    StudyScheduleDetailSerializer,
)


class GroupScheduleListCreateView(APIView):
    """
    스터디 그룹 일정 목록 조회 및 생성 (REQ-SCHD-001, REQ-SCHD-002)
    """

    permission_classes = (permissions.IsAuthenticated,)

    @extend_schema(
        operation_id="ListGroupSchedules",
        responses={
            200: OpenApiResponse(description="그룹 내 스케줄 목록 조회 성공"),
            404: OpenApiResponse(description="스터디 그룹을 찾을 수 없음"),
        },
        tags=["StudyGroupSchedule"],
        summary="스터디 스케줄 목록 조회",
        description="특정 스터디 그룹의 모든 스케줄을 조회합니다.",
    )
    def get(self, request: Request, group_uuid: uuid.UUID) -> Response:
        study_group = get_object_or_404(StudyGroup, uuid=group_uuid)
        schedules = GroupSchedule.objects.filter(study_group=study_group).order_by("session_date", "start_time")
        serializer = StudyScheduleDetailSerializer(schedules, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

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
        ),
        examples=[
            OpenApiExample(
                "Create Schedule Example",
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
    def post(self, request: Request, group_uuid: uuid.UUID) -> Response:
        study_group = get_object_or_404(StudyGroup, uuid=group_uuid)
        serializer = GroupScheduleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        exists = GroupSchedule.objects.filter(
            study_group=study_group,
            session_date=serializer.validated_data["session_date"],
            start_time=serializer.validated_data["start_time"],
        ).exists()

        if exists:
            return Response({"detail": "같은 시간대에 이미 스케줄이 존재합니다."}, status=409)

        serializer.save(study_group=study_group)
        return Response(serializer.data, status=201)


class GroupScheduleDetailUpdateDeleteView(APIView):
    """
    개별 스케줄 상세 조회, 수정, 삭제 (REQ-SCHD-003, REQ-SCHD-004)
    """

    permission_classes = (permissions.IsAuthenticated,)

    @extend_schema(
        operation_id="RetrieveGroupSchedule",
        responses={
            200: OpenApiResponse(description="스케줄 상세 조회 성공"),
            404: OpenApiResponse(description="스케줄을 찾을 수 없음"),
        },
        tags=["StudyGroupSchedule"],
        summary="스터디 스케줄 상세 조회",
    )
    def get(self, request: Request, group_uuid: uuid.UUID, schedule_uuid: uuid.UUID) -> Response:
        schedule = get_object_or_404(GroupSchedule, uuid=schedule_uuid, study_group__uuid=group_uuid)
        serializer = StudyScheduleDetailSerializer(schedule)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        operation_id="UpdateGroupSchedule",
        request=GroupScheduleCreateSerializer,
        responses={
            200: OpenApiResponse(description="스케줄 수정 성공"),
            404: OpenApiResponse(description="스케줄을 찾을 수 없음"),
        },
        tags=["StudyGroupSchedule"],
        summary="스터디 스케줄 수정",
    )
    def patch(self, request: Request, group_uuid: uuid.UUID, schedule_uuid: uuid.UUID) -> Response:
        schedule = get_object_or_404(GroupSchedule, uuid=schedule_uuid, study_group__uuid=group_uuid)
        serializer = GroupScheduleCreateSerializer(schedule, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        operation_id="DeleteGroupSchedule",
        responses={
            204: OpenApiResponse(description="스케줄 삭제 성공"),
            404: OpenApiResponse(description="스케줄을 찾을 수 없음"),
        },
        tags=["StudyGroupSchedule"],
        summary="스터디 스케줄 삭제",
    )
    def delete(self, request: Request, group_uuid: uuid.UUID, schedule_uuid: uuid.UUID) -> Response:
        schedule = get_object_or_404(GroupSchedule, uuid=schedule_uuid, study_group__uuid=group_uuid)
        schedule.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
