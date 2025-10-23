from typing import Any

from rest_framework import serializers

from apps.recruitments.models.bookmark import Bookmark


class BookmarkSerializer(serializers.ModelSerializer[Bookmark]):

    class Meta:
        model = Bookmark
        fields = ["user_id", "recruitment_id", "created_at"]
        extra_kwargs = {
            "user_id": {"read_only": True},
            "created_at": {"read_only": True},
        }

    def create(self, validated_data: dict[str, Any]) -> Bookmark:

        return Bookmark(**validated_data)
