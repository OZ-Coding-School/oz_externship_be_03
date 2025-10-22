import asyncio
import json
from typing import AsyncGenerator

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt

from apps.notifications.models import Notification


@csrf_exempt
@login_required
async def notification_stream(request: HttpRequest) -> StreamingHttpResponse:
    async def event_stream() -> AsyncGenerator[str, None]:
        # 연결 완료 신호
        yield f"data:{json.dumps({'type':'connected'})}\n\n"

        while True:
            # user.id가 None일 가능성 체크
            if request.user.id is None:
                yield f"data:{json.dumps({'type':'error','message':'User not authenticated'})}\n\n"
                break
            # DB 쿼리
            notifications = Notification.objects.filter(
                user_id=request.user.id,
                is_read=False
            )

            # 새 알림이 있으면 전송
            if notifications:
                notifications_data = []
                notification_ids = []
                for notification in notifications:
                    data = {
                        "id": notification.id,
                        "content": notification.content,
                        "type": notification.type,
                        "back_url_link": notification.back_url_link,
                        "created_at": notification.created_at.isoformat(),
                        "is_read": notification.is_read,
                    }
                    notifications_data.append(data)

                    Notification.objects.filter(
                        id__in=notification_ids
                    ).update(is_read=True)

                # 클라이언트에 전송
                yield f"data: {json.dumps({'type': 'notifications', 'data': notifications_data})}\n\n"

            # 폴링 주기 (새로운 알림 있나요?)
            await asyncio.sleep(1)

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["Connection"] = "keep-alive"

    return response
