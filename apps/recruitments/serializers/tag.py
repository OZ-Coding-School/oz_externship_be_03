from rest_framework import serializers

from apps.recruitments.models import Tag


class TagSerializer(serializers.ModelSerializer[Tag]):
    """태그 모델 직렬화기"""

    class Meta:
        model = Tag
        fields = ["id", "name"]
