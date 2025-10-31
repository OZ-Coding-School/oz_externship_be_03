from rest_framework import serializers


class MemberKickSerializer(serializers.Serializer):  # type: ignore[type-arg]
    """REQ-STDY-006: 리더가 특정 멤버를 추방할 때 사용"""

    member_id = serializers.IntegerField(required=True, min_value=1, help_text="추방할 멤버의 GroupMember ID")


class MemberLeaveSerializer(serializers.Serializer):  # type: ignore[type-arg]
    """REQ-STDY-007: 멤버 자진 탈퇴 요청용"""

    confirm = serializers.BooleanField(required=True, help_text="탈퇴 의사 확인 (true 입력 시 실행)")


class DelegateLeaderSerializer(serializers.Serializer):  # type: ignore[type-arg]
    """REQ-STDY-008: 리더 위임 요청 및 결과 직렬화"""

    # 요청용
    target_member_id = serializers.IntegerField(
        required=True,
        min_value=1,
        help_text="리더로 위임할 대상 멤버의 GroupMember ID",
    )

    # 응답용
    previous_leader_id = serializers.IntegerField(read_only=True)
    new_leader_id = serializers.IntegerField(read_only=True)
    message = serializers.CharField(
        default="리더가 성공적으로 위임되었습니다.",
        read_only=True,
    )
