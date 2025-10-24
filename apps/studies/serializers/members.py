from rest_framework import serializers


class KickMemberSerializer(serializers.Serializer[None]):
    """REQ-STDY-006: 스터디 그룹 멤버 추방 API"""

    pass


class LeaveGroupSerializer(serializers.Serializer[None]):
    """REQ-STDY-007: 스터디 그룹 자진 탈퇴 API"""

    pass


class DelegateLeaderSerializer(serializers.Serializer):  # type: ignore[type-arg]
    """REQ-STDY-008: 리더 위임 요청 시 사용되는 입력값 검증"""

    target_user_id = serializers.IntegerField(
        required=True,
        min_value=1,  # DB에 존재할 수 없는 값 방어용
        help_text="리더로 위임할 대상 멤버의 유저 ID",
    )
