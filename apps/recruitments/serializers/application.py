from rest_framework.serializers import ModelSerializer

from apps.recruitments.models.application import Application


class ApplicationSerializer(ModelSerializer[Application]):
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
