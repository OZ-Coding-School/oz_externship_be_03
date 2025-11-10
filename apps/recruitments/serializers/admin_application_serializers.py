from rest_framework import serializers

from apps.lecture.models import CrawledLecture
from apps.recruitments.models import Application, Recruitment, Tag
from apps.users.models import User

DATETIME_FORMAT = "%Y-%m-%d %H:%M"


class AdminApplicationAuthorSerializer(serializers.ModelSerializer[User]):
    class Meta:
        model = User
        fields = ["id", "nickname", "email"]
        read_only_fields = fields


class AdminApplicationRecruitmentSerializer(serializers.ModelSerializer[Recruitment]):
    class Meta:
        model = Recruitment
        fields = ["id", "title"]
        read_only_fields = fields


class AdminApplicationSerializer(serializers.ModelSerializer[Application]):
    user = AdminApplicationAuthorSerializer()
    recruitment = AdminApplicationRecruitmentSerializer()
    status_display = serializers.CharField(source="get_status_display")

    class Meta:
        model = Application
        fields = ["id", "user", "recruitment", "status", "status_display", "created_at", "updated_at"]
        read_only_fields = fields
        extra_kwargs = {
            "created_at": {"format": DATETIME_FORMAT},
            "updated_at": {"format": DATETIME_FORMAT},
        }


class AdminApplicationDetailAuthorSerializer(AdminApplicationAuthorSerializer):
    gender_display = serializers.CharField(source="get_gender_display")

    class Meta:
        model = User
        fields = ["id", "email", "gender", "gender_display", "profile_img_url"]
        read_only_fields = fields


class RecruitmentLectureSerializer(serializers.ModelSerializer[CrawledLecture]):
    class Meta:
        model = CrawledLecture
        fields = ["id", "title", "instructor", "thumbnail_img_url", "platform", "url_link"]
        read_only_fields = fields


class RecruitmentTagSerializer(serializers.ModelSerializer[Tag]):
    class Meta:
        model = Tag
        fields = ["id", "name"]
        read_only_fields = fields


class AdminApplicationDetailRecruitmentSerializer(AdminApplicationRecruitmentSerializer):
    lectures = RecruitmentLectureSerializer(source="study_group.lectures")
    tags = RecruitmentTagSerializer()

    class Meta:
        model = Recruitment
        fields = ["id", "title", "expected_headcount", "close_at", "lectures", "tags"]
        read_only_fields = fields
        extra_kwargs = {
            "close_at": {"format": DATETIME_FORMAT},
        }


class AdminApplicationDetailSerializer(serializers.ModelSerializer[Application]):
    user = AdminApplicationDetailAuthorSerializer(
        read_only=True,
    )
    recruitment = AdminApplicationDetailRecruitmentSerializer()
    status_display = serializers.CharField(source="get_status_display")

    class Meta:
        model = Application
        fields = [
            "id",
            "user",
            "recruitment",
            "self_introduction",
            "motivation",
            "objective",
            "has_study_experience",
            "study_experience",
            "available_time",
            "status",
            "status_display",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
        extra_kwargs = {
            "created_at": {"format": DATETIME_FORMAT},
            "updated_at": {"format": DATETIME_FORMAT},
        }
