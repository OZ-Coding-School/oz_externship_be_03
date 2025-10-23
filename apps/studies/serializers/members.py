from rest_framework import serializers


class KickMemberSerializer(serializers.Serializer[None]):
    """REQ-STDY-006: 스터디 그룹 멤버 추방 API"""

    reason = serializers.CharField(
        required=False,
        allow_blank=True,  # 선택적으로 허용 사유없이 추방하고 싶을 때를 위해 추가
        max_length=200,
        help_text="추방 사유",
    )


class LeaveGroupSerializer(serializers.Serializer[None]):
    """REQ-STDY-007: 스터디 그룹 자진 탈퇴 API"""

    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=200,
        help_text="스터디 그룹 탈퇴 사유 (선택)",
    )
    member_id = serializers.IntegerField(
        required=True,
        min_value=1,
        help_text="탈퇴할 멤버의 사용자 ID",
    )


class DelegateLeaderSerializer(serializers.Serializer):  # type: ignore[type-arg]
    """REQ-STDY-008: 리더 위임 요청 시 사용되는 입력값 검증"""

    target_user_id = serializers.IntegerField(
        required=True,
        min_value=1,  # DB에 존재할 수 없는 값 방어용
        help_text="리더로 위임할 대상 멤버의 유저 ID",
    )

    def validate_target_member_id(self, value: int) -> int:
        if value <= 0:
            raise serializers.ValidationError("유효한 멤버 ID를 입력해야 합니다.")
        return value
