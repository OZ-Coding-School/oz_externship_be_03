from typing import Any

from rest_framework import serializers

from apps.recruitments.models.bookmark import Bookmark
from apps.recruitments.services.bookmark import create_bookmark


class BookmarkSerializer(serializers.ModelSerializer[Bookmark]):
    recruitment_id = serializers.IntegerField(write_only=True, required=True)

    class Meta:
        model = Bookmark
        fields = ["uuid", "user", "recruitment_id", "recruitment", "created_at"]
        extra_kwargs = {
            "uuid": {"read_only": True},
            "user": {"read_only": True},
            "recruitment": {"read_only": True},
            "created_at": {"read_only": True},
        }

    def create(self, validated_data: dict[str, Any]) -> Bookmark:
        user = self.context["request"].user
        recruitment_id = validated_data.pop("recruitment_id")
        return create_bookmark(user, recruitment_id)
