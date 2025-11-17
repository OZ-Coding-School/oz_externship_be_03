from rest_framework import serializers


class MemberKickSerializer(serializers.Serializer):  # type: ignore[type-arg]
    """REQ-STDY-006: 리더가 특정 멤버를 추방할 때 사용"""

    target_member_uuid = serializers.UUIDField(required=True)


class MemberLeaveSerializer(serializers.Serializer):  # type: ignore[type-arg]
    """REQ-STDY-007: 멤버 자진 탈퇴 요청용"""

    pass


class DelegateLeaderSerializer(serializers.Serializer):  # type: ignore[type-arg]
    """REQ-STDY-008: 리더 위임 요청 및 결과 직렬화"""

    target_member_uuid = serializers.UUIDField(required=True)
    previous_leader_id = serializers.IntegerField(read_only=True)
    new_leader_id = serializers.IntegerField(read_only=True)
