import asyncio
import json
from typing import AsyncGenerator

from asgiref.sync import sync_to_async
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt

from apps.notifications.events import notification_events
from apps.notifications.models import Notification


@csrf_exempt
@login_required
async def notification_stream(request: HttpRequest) -> StreamingHttpResponse:
    async def event_stream() -> AsyncGenerator[str, None]:
        # 연결 완료 신호
        yield f"data:{json.dumps({'type':'connected'})}\n\n"

        # user.id가 None일 가능성 체크
        if request.user.id is None:
            yield f"data:{json.dumps({'type':'error','message':'User not authenticated'})}\n\n"
            return

        user_id: int = request.user.id

        # 이벤트 기반 대기 루프
        while True:
            # Signal에서 보낸 트리거 대기(blocking)
            has_new_notifcation = await sync_to_async(notification_events.wait_for_notification)(user_id, timeout=5.0)

            if has_new_notifcation:
                # 트리거 받으면 새 알림 조회
                latest_notification = await sync_to_async(
                    lambda: Notification.objects.filter(user_id=user_id, is_read=False).order_by("-created_at").first()
                )()

                if latest_notification:
                    data = {
                        "id": latest_notification.id,
                        "content": latest_notification.content,
                        "type": latest_notification.type,
                        "back_url_link": latest_notification.back_url_link,
                        "created_at": latest_notification.created_at.isoformat(),
                        "is_read": latest_notification.is_read,
                    }

                    yield f"data: {json.dumps({'type': 'notifications', 'data': data})}\n\n"

                await asyncio.sleep(0.1)

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["Connection"] = "keep-alive"

    return response
