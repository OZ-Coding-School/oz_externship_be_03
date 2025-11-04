from typing import Any

from rest_framework import serializers

from apps.recruitments.models.bookmark import Bookmark
from apps.recruitments.models.recruitments import Recruitment


class BookmarkSerializer(serializers.ModelSerializer[Bookmark]):
    recruitment_id = serializers.IntegerField(write_only=True, required=True)

    class Meta:
        model = Bookmark
        fields = ["uuid", "user", "recruitment_id", "recruitment", "created_at"]
        extra_kwargs = {
            "uuid": {"read_only": True},
            "user": {"read_only": True},
            "recruitment_id": {"read_only": True},
            "recruitment": {"read_only": True},
            "created_at": {"read_only": True},
        }

    def create(self, validated_data: dict[str, Any]) -> Bookmark:
        recruitment_id = validated_data.pop("recruitment_id")
        user = self.context["request"].user

        # 존재하지 않는 공고 안내
        try:
            recruitment = Recruitment.objects.get(id=recruitment_id)
        except Recruitment.DoesNotExist:
            raise serializers.ValidationError({"detail": "존재하지 않는 모집글입니다."})

        # 중복 방지
        if Bookmark.objects.filter(user=user, recruitment=recruitment).exists():
            raise serializers.ValidationError({"detail": "이미 북마크한 모집글입니다."})

        bookmark = Bookmark.objects.create(user=user, recruitment=recruitment, **validated_data)
        return bookmark
