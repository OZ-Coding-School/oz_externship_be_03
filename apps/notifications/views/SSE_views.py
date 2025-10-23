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

        #
        initial_notifications = await sync_to_async(
            lambda: list(Notification.objects.filter(
                user_id=request.user.id,
                is_read=False
            ))
        )()

            # 새 알림이 있으면 전송
        if initial_notifications:
            notifications_data = []
            notification_ids = []
            for notification in initial_notifications:
                notification_ids.append(notification.id)
                data = {
                    "id": notification.id,
                    "content": notification.content,
                    "type": notification.type,
                    "back_url_link": notification.back_url_link,
                    "created_at": notification.created_at.isoformat(),
                    "is_read": notification.is_read,
                }
                notifications_data.append(data)

            await sync_to_async(
                Notification.objects.filter(id__in=notification_ids).update
            )(is_read=True)

            # 클라이언트에 전송
            yield f"data: {json.dumps({'type': 'notifications', 'data': notifications_data})}\n\n"

        #이벤트 기반 대기 루프
        while True:
            # Signal에서 보낸 트리거 대기(blocking)
            has_new_notifcation = await sync_to_async(
                notification_events.wait_for_notification
            )(request.user.id, timeout=5.0)

            if has_new_notifcation:
                #트리거 받으면 새 알림 조회
                new_notifications = await sync_to_async(
                    lambda: list(Notification.objects.filter(
                        user_id=request.user.id,
                        is_read=False
                    ))
                )()

                if new_notifications:
                    notifications_data = []
                    notification_ids = []
                    for notification in new_notifications:
                        notification_ids.append(notification.id)
                        data = {
                            "id": notification.id,
                            "content": notification.content,
                            "type": notification.type,
                            "back_url_link": notification.back_url_link,
                            "created_at": notification.created_at.isoformat(),
                            "is_read": notification.is_read,
                        }
                        notifications_data.append(data)

                    await sync_to_async(
                        Notification.objects.filter(id__in=notification_ids).update
                    )(is_read=True)

                    yield f"data: {json.dumps({'type': 'notifications', 'data': notifications_data})}\n\n"

                await asyncio.sleep(0.1)

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["Connection"] = "keep-alive"

    return response
