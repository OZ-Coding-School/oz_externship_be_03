from datetime import date, datetime
from typing import Any, Optional, cast

from django.db.models import QuerySet
from django.utils import timezone
from rest_framework import serializers
from rest_framework.request import Request

from apps.studies.models.groups import GroupMember, StudyGroup, StudyLecture


# 스터디 그룹 생성 / 수정 (REQ-STDY-001, 003, 009)
class StudyGroupCreateSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    name = serializers.CharField(required=True, allow_blank=False)
    lectures = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
        help_text="강의 ID 목록 (선택사항, 최대 5개 지정 가능)",
    )

    class Meta:
        model = StudyGroup
        fields = [
            "id",
            "name",
            "introduction",
            "profile_img_url",
            "max_headcount",
            "start_at",
            "end_at",
            "status",
            "lectures",
        ]
        read_only_fields = ["status"]

    def to_internal_value(self, data: dict[str, Any]) -> Any:
        """Date 혹은 DateTime 문자열 모두 허용"""
        for field in ["start_at", "end_at"]:
            value = data.get(field)
            if isinstance(value, date) and not isinstance(value, datetime):
                # date 객체 → datetime 변환
                data[field] = datetime.combine(value, datetime.min.time())
            elif isinstance(value, str):
                # ISO8601 / date 문자열 모두 수용
                try:
                    data[field] = datetime.fromisoformat(value)
                except ValueError:
                    try:
                        data[field] = datetime.strptime(value, "%Y-%m-%d")
                    except ValueError:
                        raise serializers.ValidationError({field: "날짜 형식이 잘못되었습니다."})
        return super().to_internal_value(data)

    def validate_name(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("스터디 그룹 명칭은 필수 항목입니다.")
        return value

    def validate_max_headcount(self, value: int) -> int:
        if not 2 <= value <= 10:
            raise serializers.ValidationError("최대 인원 수는 2명 이상 10명 이하로 설정해야 합니다.")
        return value

    def validate_lectures(self, value: list[int]) -> list[int]:
        if len(value) > 5:
            raise serializers.ValidationError("강의는 최대 5개까지만 선택할 수 있습니다.")
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        start = attrs.get("start_at")
        end = attrs.get("end_at")
        today = timezone.now().date()

        if start and end and end < start:
            raise serializers.ValidationError({"end_at": "종료일은 시작일 이후여야 합니다."})
        if start and start.date() < today:
            raise serializers.ValidationError({"start_at": "시작일은 오늘 이후여야 합니다."})
        return attrs


# 스터디 그룹 목록 조회 (REQ-STDY-004)
class StudyGroupListSerializer(serializers.ModelSerializer[StudyGroup]):
    current_members = serializers.SerializerMethodField()
    is_leader = serializers.SerializerMethodField()
    lectures = serializers.SerializerMethodField()

    class Meta:
        model = StudyGroup
        fields = [
            "id",
            "name",
            "profile_img_url",
            "current_members",
            "max_headcount",
            "is_leader",
            "start_at",
            "end_at",
            "status",
            "lectures",
        ]

    def get_current_members(self, obj: StudyGroup) -> int:
        members: "QuerySet[GroupMember]" = obj.members.all()
        return int(members.count())

    def get_is_leader(self, obj: StudyGroup) -> bool:
        request = cast(Request | None, self.context.get("request"))
        user = getattr(request, "user", None)
        if not user or not getattr(user, "id", None):
            return False
        members: "QuerySet[GroupMember]" = obj.members.all()
        return bool(members.filter(user_id=user.id, is_leader=True).exists())

    def get_lectures(self, obj: StudyGroup) -> list[dict[str, str]]:
        return [
            {"title": "Python 심화", "instructor": "홍길동"},
            {"title": "Django 입문", "instructor": "이몽룡"},
        ]


# 스터디 멤버 정보 (REQ-STDY-005, 006, 007, 008)
class GroupMemberSerializer(serializers.ModelSerializer[GroupMember]):
    nickname = serializers.CharField(source="user.nickname", read_only=True)

    class Meta:
        model = GroupMember
        fields = ["id", "user_id", "nickname", "is_leader", "created_at"]


# 스터디 강의 정보 (REQ-STDY-002, 005)
class StudyLectureSerializer(serializers.ModelSerializer[StudyLecture]):
    title = serializers.CharField(read_only=True)
    instructor = serializers.CharField(read_only=True)
    thumbnail_url = serializers.URLField(read_only=True)
    link = serializers.URLField(read_only=True)

    class Meta:
        model = StudyLecture
        fields = [
            "id",
            "title",
            "instructor",
            "thumbnail_url",
            "link",
            "created_at",
        ]


# 스터디 그룹 상세 조회 (REQ-STDY-005)
class StudyGroupDetailSerializer(serializers.ModelSerializer[StudyGroup]):
    members = GroupMemberSerializer(many=True, read_only=True)
    lectures = StudyLectureSerializer(many=True, read_only=True)
    current_members = serializers.SerializerMethodField()

    class Meta:
        model = StudyGroup
        fields = [
            "id",
            "name",
            "introduction",
            "profile_img_url",
            "max_headcount",
            "current_members",
            "start_at",
            "end_at",
            "status",
            "members",
            "lectures",
        ]

    def get_current_members(self, obj: StudyGroup) -> int:
        members: "QuerySet[GroupMember]" = obj.members.all()
        return int(members.count())


# 관리자 전용 목록 / 상세 (REQ-STDY-011, 012)
class AdminStudyGroupListSerializer(serializers.ModelSerializer[StudyGroup]):
    current_members = serializers.SerializerMethodField()

    class Meta:
        model = StudyGroup
        fields = [
            "id",
            "name",
            "profile_img_url",
            "max_headcount",
            "current_members",
            "start_at",
            "end_at",
            "status",
            "created_at",
            "updated_at",
        ]

    def get_current_members(self, obj: StudyGroup) -> int:
        members: "QuerySet[GroupMember]" = obj.members.all()
        return int(members.count())


class AdminStudyGroupDetailSerializer(serializers.ModelSerializer[StudyGroup]):
    members = GroupMemberSerializer(many=True, read_only=True)
    lectures = StudyLectureSerializer(many=True, read_only=True)
    current_members = serializers.SerializerMethodField()

    class Meta:
        model = StudyGroup
        fields = [
            "id",
            "name",
            "introduction",
            "profile_img_url",
            "max_headcount",
            "current_members",
            "start_at",
            "end_at",
            "status",
            "members",
            "lectures",
            "created_at",
            "updated_at",
        ]

    def get_current_members(self, obj: StudyGroup) -> int:
        members: "QuerySet[GroupMember]" = obj.members.all()
        return int(members.count())
