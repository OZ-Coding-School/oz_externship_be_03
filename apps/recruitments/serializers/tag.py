from rest_framework import serializers

from apps.recruitments.models.tag import Tag


class TagSerializer(serializers.ModelSerializer[Tag]):
    id: serializers.IntegerField = serializers.IntegerField(read_only=True)
    name: serializers.CharField = serializers.CharField(
        max_length=20,
        help_text="태그 이름 (최대 20자)",
    )

    class Meta:
        model = Tag
        fields = ["id", "name"]
        read_only_fields = ["id"]
