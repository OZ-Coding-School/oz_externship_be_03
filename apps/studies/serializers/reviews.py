from __future__ import annotations

from hashlib import blake2b
from typing import Any, Dict, Optional, cast

from rest_framework import serializers
from rest_framework.request import Request

from apps.lecture.models import RatingEnum
from apps.studies.models.groups import StudyGroup
from apps.studies.models.reviews import Review


class StarRatingField(serializers.ChoiceField):
    ENUM_TO_INT: Dict[str, int] = {
        RatingEnum.ONE: 1,
        RatingEnum.TWO: 2,
        RatingEnum.THREE: 3,
        RatingEnum.FOUR: 4,
        RatingEnum.FIVE: 5,
    }
    INT_TO_ENUM: Dict[int, str] = {v: k for k, v in ENUM_TO_INT.items()}

    def __init__(self, represent: str = "int", **kwargs: Any) -> None:
        super().__init__(choices=[c[0] for c in RatingEnum.choices], **kwargs)
        assert represent in ("int", "enum")
        self.represent = represent

    def to_internal_value(self, data: Any) -> str:
        if isinstance(data, int):
            if data not in self.INT_TO_ENUM:
                raise serializers.ValidationError("별점은 1~5 사이의 정수여야 합니다.")
            return self.INT_TO_ENUM[data]
        if isinstance(data, str):
            return super().to_internal_value(data)
        raise serializers.ValidationError("별점은 enum 문자열 또는 1~5 정수여야 합니다.")

    def to_representation(self, value: Any) -> Any:
        enum_value = str(value)
        if self.represent == "enum":
            return enum_value
        return self.ENUM_TO_INT.get(enum_value, 0)


class ReviewCreateSerializer(serializers.ModelSerializer[Review]):
    star_rating = StarRatingField(represent="int")
    study_group = serializers.PrimaryKeyRelatedField(queryset=StudyGroup.objects.all())

    class Meta:
        model = Review
        fields = ("study_group", "star_rating", "content")

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        content = attrs.get("content")
        if content is not None and not str(content).strip():
            raise serializers.ValidationError({"content": ["내용이 비어 있습니다."]})
        return attrs

    def create(self, validated_data: Dict[str, Any]) -> Review:
        return Review.objects.create(user=self.context["request"].user, **validated_data)


class ReviewListItemSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField(read_only=True, source="uuid")
    rating = StarRatingField(read_only=True, source="star_rating")
    content = serializers.CharField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    is_mine = serializers.SerializerMethodField()

    def get_is_mine(self, obj: Any) -> bool:
        request = self.context.get("request")
        return bool(request and getattr(request, "user", None) and obj.user_id == request.user.id)
