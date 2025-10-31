import json
from typing import AsyncGenerator

from django.http import HttpRequest, StreamingHttpResponse

from apps.notifications.services.redis_pubsub_classify import notification_pubsub


async def notification_stream(request: HttpRequest, user_id: int) -> StreamingHttpResponse:
    # 인증 체크
    if not request.user.is_authenticated:
        return StreamingHttpResponse(
            f'data: {json.dumps({"error":"로그인이 필요합니다"},ensure_ascii=False)}\\n\\n',
            content_type="text/event-stream",
            status=401,
        )

    if request.user.id != user_id:
        return StreamingHttpResponse(
            f'data: {json.dumps({"error":"인증되지 않은 사용자"},ensure_ascii=False)}\n\n',
            content_type="text/event-stream",
            status=403,
        )

    async def async_event_stream() -> AsyncGenerator[str, None]:
        try:  # 연결 완료 신호
            yield f"data:{json.dumps({'type':'connected'}, ensure_ascii=False)}\n\n"

            # Redis 구독 처리
            async for notification in notification_pubsub.subscribe_notification(user_id=user_id):
                sse_data = json.dumps(notification, ensure_ascii=False)
                yield f"data:{sse_data}\n\n"

        except Exception as e:
            yield f"data:{json.dumps({'type':'error','message':str(e)},ensure_ascii=False)}\n\n"

    response = StreamingHttpResponse(async_event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["Connection"] = "keep-alive"

    return response
