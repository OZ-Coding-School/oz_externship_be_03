from datetime import timedelta
from typing import Any, Iterable

from django.utils import timezone
from rest_framework import serializers

from apps.studies.models.groups import StudyGroup


class StudyGroupBaseSerializer(serializers.ModelSerializer[StudyGroup]):

    class Meta:
        model = StudyGroup
        fields = [
            "id",
            "name",
            "profile_img_url",
            "max_headcount",
            "start_at",
            "end_at",
            "status",
        ]
        read_only_fields = ["id", "status"]


# 스터디 그룹 생성 / 수정
class StudyGroupCreateSerializer(StudyGroupBaseSerializer):
    name = serializers.CharField(required=True, allow_blank=False, help_text="스터디 그룹명 (필수, 공백 불가)")
    introduction = serializers.CharField(
        required=False, allow_blank=True, help_text="스터디 소개글 (선택사항, 최대 500자)"
    )
    profile_img_url = serializers.URLField(required=False, allow_null=True, help_text="프로필 이미지 URL (선택사항)")
    max_headcount = serializers.IntegerField(help_text="최대 인원 수 (2~10명)")
    start_at = serializers.DateTimeField(help_text="스터디 시작일")
    end_at = serializers.DateTimeField(help_text="스터디 종료일")
    lectures = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
        default=list,
        help_text="강의 ID 목록 (선택사항, 최대 5개 지정 가능)",
    )

    class Meta(StudyGroupBaseSerializer.Meta):
        fields = StudyGroupBaseSerializer.Meta.fields + ["introduction", "lectures"]

    # 그룹명 필수 검증
    def validate_name(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("스터디 그룹 명칭은 필수 항목입니다.")
        return value

    # 인원 수 제한 (2~10명)
    def validate_max_headcount(self, value: int) -> int:
        if not 2 <= value <= 10:
            raise serializers.ValidationError("최대 인원 수는 2명 이상 10명 이하로 설정해야 합니다.")
        return value

    # 강의 개수 제한 (최대 5개)
    def validate_lectures(self, value: list[int]) -> list[int]:
        if len(value) > 5:
            raise serializers.ValidationError("강의는 최대 5개까지만 선택할 수 있습니다.")
        return value

    # 날짜 간 관계 검증
    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        start = attrs.get("start_at")
        end = attrs.get("end_at")
        today = timezone.now().date()

        if start and end and end < start + timedelta(days=5):
            raise serializers.ValidationError({"end_at": "종료일은 시작일보다 5일 이상 이후여야 합니다."})
        if start and start.date() < today:
            raise serializers.ValidationError({"start_at": "시작일은 오늘 또는 이후여야 합니다."})
        return attrs


# 스터디 그룹 목록 조회
class StudyGroupListSerializer(StudyGroupBaseSerializer):
    current_headcount = serializers.SerializerMethodField()
    # 로그인 사용자가 리더인지 여부
    is_leader = serializers.SerializerMethodField()
    lectures = serializers.SerializerMethodField()

    class Meta(StudyGroupBaseSerializer.Meta):
        fields = StudyGroupBaseSerializer.Meta.fields + [
            "current_headcount",
            "is_leader",
            "lectures",
            "review_count",
            "star_rating_average",
            "is_reviewed",
        ]

    def get_current_headcount(self, obj: StudyGroup) -> int:
        return len(obj.members.all())

    def get_is_leader(self, obj: StudyGroup) -> bool:
        request = self.context.get("request")
        if not request or not hasattr(request, "user"):
            return False
        user = request.user
        return obj.members.filter(user_id=user.id, is_leader=True).exists()

    def get_lectures(self, obj: StudyGroup) -> list[dict[str, int | str]]:
        return [
            {
                "id": study_lecture.lecture.id,
                "title": study_lecture.lecture.title,
                "instructor": study_lecture.lecture.instructor,
            }
            for study_lecture in obj.lectures.all()
        ]


# Spec API용 시리얼라이저
class StudyGroupLectureSerializer:
    def __init__(self, data: Iterable[Any], many: bool = False) -> None:
        # dict 리스트로 변환
        self.data = [
            {"id": sl.lecture.id, "title": sl.lecture.title, "instructor": sl.lecture.instructor} for sl in data
        ]


# Spec API용 시리얼라이저
class StudyGroupMemberSerializer:
    def __init__(self, data: Iterable[Any], many: bool = False) -> None:
        self.data = [{"id": sl.user.id, "nickname": sl.user.nickname, "is_leader": sl.is_leader} for sl in data]


class StudyGroupDetailSerializer(StudyGroupBaseSerializer):
    current_headcount = serializers.SerializerMethodField()
    members = serializers.SerializerMethodField()
    lectures = serializers.SerializerMethodField()

    class Meta(StudyGroupBaseSerializer.Meta):
        fields = StudyGroupBaseSerializer.Meta.fields + ["current_headcount", "members", "lectures"]

    def get_current_headcount(self, obj: StudyGroup) -> int:
        return len(obj.members.all())

    def get_members(self, obj: StudyGroup) -> list[dict[str, int | str]]:
        return [
            {
                "id": group_member.user.id,
                "nickname": group_member.user.nickname,
                "is_leader": group_member.is_leader,
            }
            for group_member in obj.members.all()
        ]

    def get_lectures(self, obj: StudyGroup) -> list[dict[str, int | str | None]]:
        return [
            {
                "id": study_lecture.lecture.id,
                "thumbnail_img_url": study_lecture.lecture.thumbnail_img_url,
                "title": study_lecture.lecture.title,
                "instructor": study_lecture.lecture.instructor,
                "url_link": study_lecture.lecture.url_link,
            }
            for study_lecture in obj.lectures.all()
        ]
