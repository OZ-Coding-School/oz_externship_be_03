from datetime import time
from typing import Any
from rest_framework import serializers
from apps.studies.models.groups import StudyGroup
from apps.studies.models.schedules import GroupSchedule, ScheduleParticipant


# Base Serializer
class StudyScheduleBaseSerializer(serializers.ModelSerializer[GroupSchedule]):
    study_group = serializers.SlugRelatedField(
        queryset=StudyGroup.objects.all(),
        slug_field="uuid",
        help_text="스터디 그룹 ID",
        required=True,
    )

    # 날짜/시간 포맷 지정 (프론트 요구사항 반영)
    session_date = serializers.DateField(
        format="%Y-%m-%d",
        input_formats=["%Y-%m-%d"],
        help_text="스터디 진행일 (YYYY-MM-DD)",
    )
    start_time = serializers.TimeField(
        format="%H:%M",
        input_formats=["%H:%M", "%H:%M:%S"],
        help_text="스터디 시작 시간 (HH:MM)",
    )
    end_time = serializers.TimeField(
        format="%H:%M",
        input_formats=["%H:%M", "%H:%M:%S"],
        help_text="스터디 종료 시간 (HH:MM)",
    )
    created_at = serializers.DateTimeField(
        format="%Y-%m-%d %H:%M",
        read_only=True,
        help_text="생성일시 (YYYY-MM-DD HH:MM)",
    )
    updated_at = serializers.DateTimeField(
        format="%Y-%m-%d %H:%M",
        read_only=True,
        help_text="수정일시 (YYYY-MM-DD HH:MM)",
    )

    class Meta:
        model = GroupSchedule
        fields = [
            "id",
            "study_group",
            "title",
            "objective",
            "session_date",
            "start_time",
            "end_time",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


# 생성 Serializer
class GroupScheduleCreateSerializer(StudyScheduleBaseSerializer):
    # Base에서 이미 포맷팅 정의했으므로, 추가 검증만 필요
    title = serializers.CharField(
        required=True,
        allow_blank=False,
        help_text="스터디 일정 제목 (필수)",
    )
    objective = serializers.CharField(
        required=True,
        allow_blank=False,
        help_text="스터디 목표 (필수)",
    )

    class Meta(StudyScheduleBaseSerializer.Meta):
        fields = StudyScheduleBaseSerializer.Meta.fields

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """시간 관계 검증"""
        start = attrs.get("start_time")
        end = attrs.get("end_time")
        if start and end and start >= end:
            raise serializers.ValidationError(
                {"end_time": "종료 시간은 시작 시간보다 이후여야 합니다."}
            )
        return attrs


# 참여자 Serializer
class ScheduleParticipantSerializer(serializers.ModelSerializer[ScheduleParticipant]):
    member_name = serializers.CharField(source="member.username", read_only=True)
    created_at = serializers.DateTimeField(
        format="%Y-%m-%d %H:%M",
        read_only=True,
    )
    updated_at = serializers.DateTimeField(
        format="%Y-%m-%d %H:%M",
        read_only=True,
    )

    class Meta:
        model = ScheduleParticipant
        fields = ["id", "member", "member_name", "is_leader", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


# 조회 Serializer (상세)
class StudyScheduleDetailSerializer(StudyScheduleBaseSerializer):
    participants = ScheduleParticipantSerializer(
        many=True,
        read_only=True,
        help_text="참여자 목록",
    )

    class Meta(StudyScheduleBaseSerializer.Meta):
        fields = StudyScheduleBaseSerializer.Meta.fields + ["participants"]
        read_only_fields = StudyScheduleBaseSerializer.Meta.read_only_fields + ["participants"]