from __future__ import annotations

import uuid
from typing import Union

from django.db.models import QuerySet
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
)
from rest_framework import permissions, status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.studies.models.groups import StudyGroup
from apps.studies.models.schedules import GroupSchedule
from apps.studies.permissions import IsGroupMember
from apps.studies.serializers.schedules import (
    ScheduleCreateSerializer,
    ScheduleDetailSerializer,
    ScheduleListSerializer,
    ScheduleUpdateSerializer,
)


class GroupScheduleListAPIView(APIView):
    """
    스터디 그룹 일정 목록 조회 및 생성 (REQ-SCHD-001, REQ-SCHD-002)
    """

    permission_classes = (permissions.IsAuthenticated, IsGroupMember)
    serializer_class = ScheduleListSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="start_date",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="일정을 시작일로 필터링 = ex(start_date=2025-11-01)",
            ),
            OpenApiParameter(
                name="end_date",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="일정을 종료일로 필터링 = ex(end_date=2025-11-01)",
            ),
        ],
        tags=["StudyGroupSchedule"],
        summary="스터디 스케줄 목록 조회",
        description="특정 스터디 그룹의 모든 스케줄을 조회합니다.",
        responses={200: ScheduleListSerializer(many=True)},
    )
    def get(self, request: Request, group_uuid: uuid.UUID) -> Response:
        try:
            study_group = StudyGroup.objects.get(uuid=group_uuid)
        except StudyGroup.DoesNotExist:
            raise NotFound({"error": f"Group uuid invalid. - group uuid: {group_uuid}"})

        self.check_object_permissions(request, study_group)

        schedules = self.get_queryset(request, study_group)
        serializer = self.serializer_class(schedules, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def get_queryset(self, request: Request, study_group: StudyGroup) -> QuerySet[GroupSchedule]:
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        qs = (
            GroupSchedule.objects.prefetch_related("participants", "participants__user")
            .filter(study_group=study_group)
            .order_by("session_date", "start_time", "end_time")
        )

        if start_date and end_date:
            qs = qs.filter(session_date__range=(start_date, end_date))
        elif start_date:
            qs = qs.filter(session_date__gte=start_date)
        elif end_date:
            qs = qs.filter(session_date__lte=end_date)

        return qs


class GroupScheduleCreateAPIView(APIView):
    permission_classes = (permissions.IsAuthenticated, IsGroupMember)
    serializer_class = ScheduleCreateSerializer

    @extend_schema(
        request=ScheduleCreateSerializer,
        tags=["StudyGroupSchedule"],
        summary="스터디 스케줄 생성",
        description=(
            "입력 항목:\n"
            "• participants: 스케줄에 참여할 멤버 uuid 목록\n"
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
                    "participants": [uuid.uuid4() for i in range(3)],
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
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        study_group = serializer.validated_data["study_group"]
        self.check_object_permissions(request, study_group)

        already_exists = GroupSchedule.objects.filter(
            study_group=study_group,
            session_date=serializer.validated_data["session_date"],
            start_time=serializer.validated_data["start_time"],
        ).exists()

        if already_exists:
            return Response({"error": "같은 시간대에 이미 스케줄이 존재합니다."}, status=status.HTTP_409_CONFLICT)

        serializer.save(study_group=study_group)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(
        tags=["StudyGroupSchedule"],
        summary="스터디 스케줄 상세조회 API",
    ),
    patch=extend_schema(
        tags=["StudyGroupSchedule"],
        summary="스터디 스케줄 업데이트 API",
        request=ScheduleUpdateSerializer,
    ),
    delete=extend_schema(
        tags=["StudyGroupSchedule"],
        summary="스터디 스케줄 삭제 API",
    ),
)
class GroupScheduleDetailUpdateDeleteView(APIView):
    """
    개별 스케줄 상세 조회, 수정, 삭제 (REQ-SCHD-003, REQ-SCHD-004)
    """

    permission_classes = (permissions.IsAuthenticated, IsGroupMember)

    def get_serializer_class(self) -> type[Union[ScheduleUpdateSerializer, ScheduleDetailSerializer]]:
        if self.request.method == "GET":
            return ScheduleDetailSerializer
        return ScheduleUpdateSerializer

    def get_object(self, schedule_uuid: uuid.UUID) -> GroupSchedule:
        try:
            schedule = GroupSchedule.objects.get(uuid=schedule_uuid)
        except GroupSchedule.DoesNotExist:
            raise NotFound({"error": f"Schedule uuid invalid. - schedule uuid: {schedule_uuid}"})
        return schedule

    def get(self, request: Request, schedule_uuid: uuid.UUID) -> Response:
        schedule = self.get_object(schedule_uuid)
        self.check_object_permissions(request, schedule.study_group)
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(schedule)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request: Request, schedule_uuid: uuid.UUID) -> Response:
        schedule = self.get_object(schedule_uuid)
        self.check_object_permissions(request, schedule.study_group)
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(schedule, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request: Request, schedule_uuid: uuid.UUID) -> Response:
        schedule = self.get_object(schedule_uuid)
        self.check_object_permissions(request, schedule.study_group)
        schedule.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
