from typing import Any

from rest_framework import serializers

from apps.recruitments.models.application import Application, ApplicationStatus


class ApplicationSerializer(serializers.ModelSerializer[Application]):
    class Meta:
        model = Application
        fields = [
            "id",
            "recruitment",
            "user",
            "objective",
            "motivation",
            "self_introduction",
            "available_time",
            "has_study_experience",
            "study_experience",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "user", "status", "created_at", "updated_at"]


class ApplicationStatusUpdateSerializer(serializers.Serializer[Any]):
    status = serializers.ChoiceField(choices=ApplicationStatus.choices)
