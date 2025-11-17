from typing import Any

from django.db import transaction
from rest_framework import serializers

from apps.studies.models import StudyGroup
from apps.studies.models.groups import GroupMember
from apps.studies.models.schedules import GroupSchedule, ScheduleParticipant
from apps.users.models import User


class ParticipantUserSerializer(serializers.ModelSerializer[User]):
    class Meta:
        model = User
        fields = ["uuid", "nickname"]


class ScheduleParticipantSerializer(serializers.ModelSerializer[GroupMember]):
    user = ParticipantUserSerializer()

    class Meta:
        model = GroupMember
        fields = ["uuid", "user", "is_leader"]


class ScheduleListSerializer(serializers.ModelSerializer[GroupSchedule]):
    class Meta:
        model = GroupSchedule
        fields = ["uuid", "title", "session_date", "start_time", "end_time"]


class ScheduleUpdateSerializer(serializers.ModelSerializer[GroupSchedule]):
    participants = serializers.SlugRelatedField(
        slug_field="uuid",
        queryset=GroupMember.objects.all(),
        many=True,
        help_text="그룹 멤버의 uuid 리스트를 입력",
    )

    class Meta:
        model = GroupSchedule
        fields = ["uuid", "participants", "title", "objective", "session_date", "start_time", "end_time"]
        extra_kwargs = {"uuid": {"read_only": True}}

    @transaction.atomic
    def update(self, instance: GroupSchedule, validated_data: dict[str, Any]) -> GroupSchedule:
        participants = validated_data.pop("participants", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        if participants is not None:
            instance.schedule_participants.set(participants, clear=True)
        return instance

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        start = attrs.get("start_time")
        end = attrs.get("end_time")
        if start and end and start >= end:
            raise serializers.ValidationError({"end_time": "종료 시간은 시작 시간보다 이후여야 합니다."})
        return attrs


class ScheduleCreateSerializer(ScheduleUpdateSerializer):
    study_group = serializers.SlugRelatedField(slug_field="uuid", queryset=StudyGroup.objects.all())

    class Meta(ScheduleUpdateSerializer.Meta):
        fields = ScheduleUpdateSerializer.Meta.fields + ["study_group"]

    @transaction.atomic
    def create(self, validated_data: dict[str, Any]) -> GroupSchedule:
        participants = validated_data.pop("participants")
        schedule = GroupSchedule.objects.create(**validated_data)
        schedule.participants.set(participants)
        return schedule


class ScheduleDetailSerializer(serializers.ModelSerializer[GroupSchedule]):
    participants = ScheduleParticipantSerializer(many=True, read_only=True)

    class Meta:
        model = GroupSchedule
        fields = ["uuid", "title", "participants", "objective", "session_date", "start_time", "end_time", "created_at"]
