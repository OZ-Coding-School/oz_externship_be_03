from rest_framework import serializers


class TagSerializer(serializers.Serializer[dict[str, str]]):
    """Mock 데이터 전용 태그 직렬화기"""

    id: serializers.IntegerField = serializers.IntegerField(required=False)
    name: serializers.CharField = serializers.CharField(
        max_length=20,
        help_text="태그 이름 (최대 20자)",
    )
