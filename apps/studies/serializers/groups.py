import math
from datetime import timedelta
from typing import Any, Dict

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.lecture.models import CrawledLecture
from apps.studies.models.groups import GroupMember, StudyGroup


class StudyGroupBaseSerializer(serializers.ModelSerializer[StudyGroup]):

    class Meta:
        model = StudyGroup
        fields = [
            "uuid",
            "name",
            "profile_img_url",
            "max_headcount",
            "start_at",
            "end_at",
            "status",
        ]
        read_only_fields = ["uuid", "status"]


# 스터디 그룹 생성 / 수정
class StudyGroupCreateSerializer(StudyGroupBaseSerializer):
    name = serializers.CharField(required=True, allow_blank=False, help_text="스터디 그룹명 (필수, 공백 불가)")
    introduction = serializers.CharField(
        required=False, allow_blank=True, help_text="스터디 소개글 (선택사항, 최대 500자)"
    )
    profile_img_url = serializers.URLField(required=False, allow_null=True, help_text="프로필 이미지 URL (선택사항)")
    max_headcount = serializers.IntegerField(help_text="최대 인원 수 (2~10명)")
    start_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", help_text="스터디 시작일")
    end_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", help_text="스터디 종료일")
    lectures = serializers.SlugRelatedField(
        queryset=CrawledLecture.objects.all(),
        many=True,
        required=False,
        allow_empty=True,
        default=list,
        help_text="강의 UUID 목록 (선택사항, 최대 5개 지정 가능)",
        slug_field="uuid",
    )

    class Meta(StudyGroupBaseSerializer.Meta):
        fields = StudyGroupBaseSerializer.Meta.fields + ["introduction", "lectures"]

    def create(self, validated_data: Dict[str, Any]) -> StudyGroup:
        lectures = validated_data.pop("lectures", [])
        # 에러 발생 시 StudyGroup도 롤백
        with transaction.atomic():
            study_group = StudyGroup.objects.create(**validated_data)
            study_group.lectures.set(lectures)
        return study_group

    def to_representation(self, instance: StudyGroup) -> Dict[str, str]:
        """출력 시 lecture 객체 → uuid 리스트로 변환"""
        ret = super().to_representation(instance)
        ret["lectures"] = list(instance.lectures.values_list("uuid", flat=True))
        return ret

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

    def update(self, instance: StudyGroup, validated_data: Dict[str, Any]) -> StudyGroup:
        lectures = validated_data.pop("lectures", None)

        for key, value in validated_data.items():
            setattr(instance, key, value)

        with transaction.atomic():
            # 엄데이트할 필드만 선택하여 업데이트
            if validated_data:
                instance.save(update_fields=list(validated_data.keys()))

            if lectures is not None:
                instance.lectures.set(lectures, clear=True)

        return instance


class StudyGroupListLectureSerializer(serializers.ModelSerializer[CrawledLecture]):
    class Meta:
        model = CrawledLecture
        fields = ("uuid", "title", "instructor", "original_price", "discount_price")


# 스터디 그룹 목록 조회
class StudyGroupListSerializer(StudyGroupBaseSerializer):
    current_headcount = serializers.IntegerField()
    is_leader = serializers.SerializerMethodField()
    lectures = StudyGroupListLectureSerializer(many=True)
    total_pages = serializers.SerializerMethodField()
    total_groups = serializers.SerializerMethodField()

    class Meta(StudyGroupBaseSerializer.Meta):
        fields = StudyGroupBaseSerializer.Meta.fields + [
            "current_headcount",
            "is_leader",
            "lectures",
            "total_pages",
            "total_groups",
        ]

    def get_is_leader(self, obj: StudyGroup) -> bool:
        request = self.context.get("request")
        if not request or not hasattr(request, "user"):
            return False
        req_user_id = request.user.id
        members = obj.group_members.all()

        return any(member.user.id == req_user_id and member.is_leader for member in members)

    def get_total_pages(self) -> int:
        total_groups = StudyGroup.objects.count()
        page_size = 9

        return math.ceil(total_groups / page_size)

    def get_total_groups(self) -> int:
        return StudyGroup.objects.count()


class StudyGroupDetailLectureSerializer(serializers.ModelSerializer[CrawledLecture]):
    class Meta:
        model = CrawledLecture
        fields = ("uuid", "thumbnail_img_url", "title", "instructor", "url_link")


class StudyGroupDetailMemberSerializer(serializers.ModelSerializer[GroupMember]):
    uuid = serializers.UUIDField(source="user.uuid")
    nickname = serializers.CharField(source="user.nickname")

    class Meta:
        model = GroupMember
        fields = ("uuid", "nickname", "is_leader")


class StudyGroupDetailSerializer(StudyGroupBaseSerializer):
    current_headcount = serializers.SerializerMethodField()
    members = StudyGroupDetailMemberSerializer(source="group_members", many=True)
    lectures = StudyGroupDetailLectureSerializer(many=True)
    is_me_leader = serializers.SerializerMethodField()

    class Meta(StudyGroupBaseSerializer.Meta):
        fields = StudyGroupBaseSerializer.Meta.fields + ["current_headcount", "members", "lectures", "is_me_leader"]

    def get_current_headcount(self, obj: StudyGroup) -> int:
        return len(obj.members.all())

    def get_is_me_leader(self, obj: StudyGroup) -> bool:
        request = self.context.get("request")
        if not request or not hasattr(request, "user"):
            return False

        return obj.members.filter(user=request.user, groupmember__is_leader=True).exists()
