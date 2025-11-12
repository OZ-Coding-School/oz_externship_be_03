from __future__ import annotations

from typing import Any, Optional

from rest_framework import serializers

from apps.recruitments.models.application import Application
from apps.recruitments.models.recruitment_images import RecruitmentImage


class MyApplicationSerializer(serializers.Serializer[Any]):

    uuid = serializers.SerializerMethodField()
    status = serializers.CharField()
    created_at = serializers.DateTimeField()
    recruitment_title = serializers.CharField(source="recruitment.title")
    recruitment_img = serializers.SerializerMethodField()
    expected_headcount = serializers.IntegerField(source="recruitment.expected_headcount")
    deadline = serializers.SerializerMethodField()

    def get_uuid(self, obj: Application) -> int | str:
        # 모델에 uuid 필드가 있으면 사용, 없으면 id를 사용
        return getattr(obj, "uuid", obj.id)

    def get_recruitment_img(self, obj: Application) -> Optional[str]:
        images = getattr(obj.recruitment, "images", None)
        first: Optional[RecruitmentImage] = None
        if images is not None:
            if isinstance(images, list):
                first = images[0] if images else None
            else:
                first = images.first()
        else:
            first = obj.recruitment.images.first()

        if first and getattr(first, "img_url", None):
            return first.img_url

        return None

    def get_deadline(self, obj: Application) -> str:
        return obj.recruitment.close_at.date().isoformat()
