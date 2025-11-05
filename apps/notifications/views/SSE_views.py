import json
from typing import AsyncGenerator

from django.http import HttpRequest, StreamingHttpResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken

from apps.notifications.services.redis_pubsub_classify import notification_pubsub
from apps.studies.models.groups import GroupMember


async def notification_stream(request: HttpRequest, user_id: int) -> StreamingHttpResponse:
    #인증 체크
    token = request.GET.get("token")
    if not token:
        return StreamingHttpResponse(
            f'data: {json.dumps({"error":"토큰이 필요합니다"}, ensure_ascii=False)}\\n\\n',
            content_type="text/event-stream",
            status=401,
        )
    try:
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)
        user_id = user.id
    except InvalidToken:
        return StreamingHttpResponse(
            f'data: {json.dumps({"error":"인증되지않은 토큰"}, ensure_ascii=False)}\\n\\n',
            content_type="text/event-stream",
            status=401,
        )

    async def async_event_stream() -> AsyncGenerator[str, None]:
        try:  # 연결 완료 신호
            yield f"data:{json.dumps({'type':'connected'}, ensure_ascii=False)}\n\n"

            # 사용자가 속한 그룹들 조회
            user_groups = [
                str(group_id)
                async for group_id in GroupMember.objects.filter(user_id=user_id).values_list(
                    "study_group_id", flat=True
                )
            ]

            # Redis 구독 처리
            async for notification in notification_pubsub.subscribe_notification(
                user_id=user_id, group_ids=user_groups if user_groups else None
            ):
                sse_data = json.dumps(notification, ensure_ascii=False)
                yield f"data:{sse_data}\n\n"

        except Exception as e:
            yield f"data:{json.dumps({'type':'error','message':str(e)},ensure_ascii=False)}\n\n"

    response = StreamingHttpResponse(async_event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["Connection"] = "keep-alive"

    return response
