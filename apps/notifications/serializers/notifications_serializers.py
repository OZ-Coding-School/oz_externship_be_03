from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from apps.notifications.models import Notification


class NotificationSerializer(ModelSerializer[Notification]):
    # 알림을 소유한 user_id만 응답 (user_id만 응답하여 DB조인 최소화)
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    # NotificationType의 한글명 반환 (ex : SYSTEM = "SYSTEM" -> "시스템 알림")
    type_display = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = Notification
        # BaseModel 에 생성 및 업데이트 자동 기록이 있으므로 exclude 사용하여 불필요한 필드 숨기는 코드
        exclude = ("created_at", "updated_at")

        # 클라이언트가 임의로 읽음 상태 필드를 수정할 수 없게 읽기 전용으로 설정하는 코드
        extra_kwargs = {
            "is_read": {"read_only": True},
        }
