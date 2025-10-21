from typing import Any

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.studies.models.groups import GroupMember, StudyGroup

User = get_user_model()


class LeaderDelegationSerializer(serializers.Serializer[Any]):
    """스터디 그룹 리더 위임 (REQ-STDY-006)"""

    target_user_id = serializers.IntegerField(help_text="리더로 위임할 사용자 ID")

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        request = self.context.get("request")
        group = self.context.get("group")

        if not request or not request.user:
            raise serializers.ValidationError("로그인이 필요합니다.")
        if not isinstance(group, StudyGroup):
            raise serializers.ValidationError("스터디 그룹 정보가 올바르지 않습니다.")

        # 요청자가 그룹 멤버인지 확인
        try:
            current_member = GroupMember.objects.get(study_group=group, user=request.user)
        except GroupMember.DoesNotExist:
            raise serializers.ValidationError("해당 스터디 그룹의 멤버가 아닙니다.")

        # 리더 여부 검증
        if not current_member.is_leader:
            raise serializers.ValidationError("리더만 접근 가능한 기능입니다.")

        # 위임 대상 유저 존재 여부 확인
        try:
            target_user = User.objects.get(id=attrs["target_user_id"])
        except User.DoesNotExist:
            raise serializers.ValidationError("해당 ID 값의 유저가 존재하지 않습니다.")

        # 대상이 스터디 그룹 멤버인지 확인
        try:
            target_member = GroupMember.objects.get(study_group=group, user=target_user)
        except GroupMember.DoesNotExist:
            raise serializers.ValidationError("해당 유저는 이 스터디 그룹의 멤버가 아닙니다.")

        # 자기 자신에게 위임 불가
        if target_member.user_id == current_member.user_id:
            raise serializers.ValidationError("자기 자신에게는 리더를 위임할 수 없습니다.")

        attrs["current_member"] = current_member
        attrs["target_member"] = target_member
        return attrs
