from rest_framework import serializers

from apps.recruitments.models import Tag


class TagSerializer(serializers.ModelSerializer):
    """태그 모델 직렬화기 (커스텀 에러 메시지 포함)"""

    name = serializers.CharField(
        required=True,
        error_messages={"required": "태그 이름은 필수입니다."},
    )

    class Meta:
        model = Tag
        fields = ["id", "name"]
