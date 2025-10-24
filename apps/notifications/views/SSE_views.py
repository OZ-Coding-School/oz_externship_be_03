import asyncio
import json
from typing import AsyncGenerator

from django.contrib.auth.decorators import login_required
from django.http import StreamingHttpResponse, HttpRequest

from apps.notifications.services.redis_pubsub_classify import notification_pubsub


@login_required
async def notification_stream(request:HttpRequest, user_id: int) -> StreamingHttpResponse:
    if request.user.id != user_id:
        return StreamingHttpResponse(
            'data: {"error":"인증되지 않은 사용자"}\n\n', content_type="text/event-stream", status=403
        )

    async def async_event_stream() -> AsyncGenerator[str, None]:
        try:  # 연결 완료 신호
            yield f"data:{json.dumps({'type':'connected'})}\n\n"

            # Redis 구독 처리
            async for notification in notification_pubsub.subscribe_user_notification(user_id):
                sse_data = json.dumps(notification, ensure_ascii=False)
                yield f"data:{sse_data}\n\n"

        except Exception as e:
            yield f"data:{json.dumps({'type':'error','message':str(e)})}\n\n"

    response = StreamingHttpResponse(async_event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["Connection"] = "keep-alive"

    return response
