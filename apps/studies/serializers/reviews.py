from __future__ import annotations

from typing import Any, Dict, Optional, cast

from rest_framework import serializers
from rest_framework.request import Request

from apps.lecture.models import RatingEnum
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
    content = serializers.CharField(allow_blank=False)

    class Meta:
        model = Review
        fields = ("star_rating", "content")

    def create(self, validated_data: Dict[str, Any]) -> Review:
        return Review.objects.create(**validated_data)


class ReviewListItemSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField(read_only=True, source="uuid")
    rating = StarRatingField(read_only=True, source="star_rating")
    content = serializers.CharField()
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M")
    updated_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M")
    is_mine = serializers.SerializerMethodField()

    def get_is_mine(self, obj: Any) -> bool:
        request: Optional[Request] = cast(Optional[Request], self.context.get("request"))
        user_id = getattr(getattr(request, "user", None), "id", None)
        return bool(user_id is not None and getattr(obj, "user_id", None) == user_id)


class ReviewUpdateSerializer(serializers.ModelSerializer[Review]):
    star_rating = StarRatingField(represent="int", required=False)
    content = serializers.CharField(required=False)

    class Meta:
        model = Review
        fields = ("star_rating", "content")

    def validate_content(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("내용이 비어 있습니다.")
        return value


DATETIME_MINUTE_FMT = "%Y-%m-%d %H:%M"


class AdminReviewListSerializer(serializers.ModelSerializer[Review]):
    """
    어드민 페이지에서 보는 리뷰 목록용
    - 고유 id (PK)
    - 스터디 그룹명
    - 작성자 닉네임/이메일
    - 별점
    - 내용
    - 생성일시, 수정일시 (YYYY-MM-DD HH:MM)
    """

    id = serializers.IntegerField(read_only=True, source="pk")
    study_group_name = serializers.CharField(read_only=True, source="study_group.name")
    user_nickname = serializers.CharField(read_only=True, source="user.nickname")
    user_email = serializers.CharField(read_only=True, source="user.email")
    star_rating = StarRatingField(read_only=True, represent="int")
    created_at = serializers.DateTimeField(format=DATETIME_MINUTE_FMT, read_only=True)
    updated_at = serializers.DateTimeField(format=DATETIME_MINUTE_FMT, read_only=True)

    class Meta:
        model = Review
        fields = (
            "id",
            "study_group_name",
            "user_nickname",
            "user_email",
            "star_rating",
            "content",
            "created_at",
            "updated_at",
        )


class AdminReviewDetailSerializer(serializers.ModelSerializer[Review]):
    """
    어드민 페이지에서 특정 리뷰 클릭했을 때 나오는 상세용
    목록보다 스터디 그룹 정보가 조금 더 많음
    """

    id = serializers.IntegerField(read_only=True, source="pk")
    study_group_id = serializers.IntegerField(read_only=True, source="study_group.id")
    study_group_uuid = serializers.UUIDField(read_only=True, source="study_group.uuid")
    study_group_name = serializers.CharField(read_only=True, source="study_group.name")
    study_group_introduction = serializers.CharField(read_only=True, source="study_group.introduction")
    study_group_start_at = serializers.DateTimeField(
        source="study_group.start_at",
        format=DATETIME_MINUTE_FMT,
        read_only=True,
    )
    study_group_end_at = serializers.DateTimeField(
        source="study_group.end_at",
        format=DATETIME_MINUTE_FMT,
        read_only=True,
    )

    user_nickname = serializers.CharField(read_only=True, source="user.nickname")
    user_email = serializers.CharField(read_only=True, source="user.email")
    star_rating = StarRatingField(read_only=True, represent="int")
    created_at = serializers.DateTimeField(format=DATETIME_MINUTE_FMT, read_only=True)
    updated_at = serializers.DateTimeField(format=DATETIME_MINUTE_FMT, read_only=True)

    class Meta:
        model = Review
        fields = (
            "id",
            "study_group_id",
            "study_group_uuid",
            "study_group_name",
            "study_group_introduction",
            "study_group_start_at",
            "study_group_end_at",
            "user_nickname",
            "user_email",
            "star_rating",
            "content",
            "created_at",
            "updated_at",
        )
