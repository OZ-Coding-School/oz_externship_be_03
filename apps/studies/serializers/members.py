from rest_framework import serializers


class LeaderDelegationSerializer(serializers.Serializer):  # type: ignore[type-arg]
    """REQ-STDY-006: 리더 위임 요청 시 사용되는 입력값 검증"""

    target_user_id = serializers.IntegerField(required=True, help_text="리더로 위임할 대상 멤버의 유저 ID")

    def validate_target_user_id(self, value: int) -> int:
        if value <= 0:
            raise serializers.ValidationError("유효한 사용자 ID를 입력해야 합니다.")
        return value
