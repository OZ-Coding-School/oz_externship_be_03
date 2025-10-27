from rest_framework import serializers

from apps.lecture.models import Category


class CategoryListSerializer(serializers.ModelSerializer[Category]):
    """카테고리 Serializer"""

    class Meta:
        model = Category
        fields = ["id", "name"]
