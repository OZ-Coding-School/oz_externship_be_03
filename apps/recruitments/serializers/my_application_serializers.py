from __future__ import annotations

from typing import Any, Optional, cast

from rest_framework import serializers

from apps.recruitments.models.application import Application
from apps.recruitments.models.recruitment_images import RecruitmentImage
from apps.recruitments.models.recruitments import Recruitment  # ← 정확한 경로 확인


class RecruitmentPresentationMixin:
    """
    - 첫 번째 이미지 URL (없으면 None)
    - close_at(DateTime) → YYYY-MM-DD
    """

    @staticmethod
    def first_url_img(recruitment: Recruitment) -> Optional[str]:
        """
        prefetch 유무에 상관없이 첫 이미지 URL 반환.
        mypy가 attr-defined를 안 내도록 staticmethod로 두기.
        """
        images = getattr(recruitment, "images", None)
        first: Optional[RecruitmentImage] = None
        if images is not None:
            if isinstance(images, list):
                first = images[0] if images else None
            else:
                first = images.first()
        else:
            first = recruitment.images.first()

        if first is None:
            return None
        # img_url이 Any로 잡히는 걸 피하기 위해 cast
        url = cast(Optional[str], getattr(first, "img_url", None))
        return url

    @staticmethod
    def deadline_date(recruitment: Recruitment) -> str:
        return recruitment.close_at.date().isoformat()


class MyApplicationSerializer(RecruitmentPresentationMixin, serializers.Serializer[Any]):
    uuid = serializers.SerializerMethodField()
    status = serializers.CharField()
    created_at = serializers.DateTimeField()
    recruitment_title = serializers.CharField(source="recruitment.title")
    recruitment_img = serializers.SerializerMethodField()
    expected_headcount = serializers.IntegerField(source="recruitment.expected_headcount")
    deadline = serializers.SerializerMethodField()

    lectures = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()

    def get_uuid(self, obj: Application) -> str:
        val = getattr(obj, "uuid", None)
        return str(val) if val is not None else str(obj.id)

    def get_recruitment_img(self, obj: Application) -> Optional[str]:
        # staticmethod 호출 → attr-defined 사라짐
        return RecruitmentPresentationMixin.first_url_img(obj.recruitment)

    def get_deadline(self, obj: Application) -> str:
        return RecruitmentPresentationMixin.deadline_date(obj.recruitment)

    def get_lectures(self, obj: Application) -> list[str]:
        """
        recruitment.study_group.lectures 의 title만 뽑아 배열로 반환.
        """
        rec = obj.recruitment
        group = getattr(rec, "study_group", None)
        if group is None:
            return []
        lectures = getattr(group, "lectures", None)
        if lectures is None:
            return []
        return list(lectures.order_by("id").values_list("title", flat=True))

    def get_tags(self, obj: Application) -> list[str]:
        rec = obj.recruitment
        tags_mgr = getattr(rec, "tags", None)
        if tags_mgr is None:
            return []
        return list(tags_mgr.order_by("id").values_list("name", flat=True))


class MyApplicationRecruitmentBriefSerializer(RecruitmentPresentationMixin, serializers.Serializer[Any]):
    uuid = serializers.UUIDField(source="recruitment.uuid", read_only=True)
    title = serializers.CharField(source="recruitment.title", read_only=True)
    recruitment_img = serializers.SerializerMethodField()
    expected_headcount = serializers.IntegerField(source="recruitment.expected_headcount", read_only=True)
    deadline = serializers.SerializerMethodField()

    def get_recruitment_img(self, obj: Application) -> Optional[str]:
        return RecruitmentPresentationMixin.first_url_img(obj.recruitment)

    def get_deadline(self, obj: Application) -> str:
        return RecruitmentPresentationMixin.deadline_date(obj.recruitment)


class MyApplicationDetailSerializer(serializers.ModelSerializer[Any]):
    recruitment = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = (
            "uuid",
            "status",
            "created_at",
            "self_introduction",
            "motivation",
            "objective",
            "available_time",
            "has_study_experience",
            "study_experience",
            "recruitment",
        )
        read_only_fields = fields

    def get_recruitment(self, obj: Application) -> dict[str, Any]:
        return MyApplicationRecruitmentBriefSerializer(obj).data
