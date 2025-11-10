from django.urls import path

from apps.chat.views import (
    ChatMessageListView,
    ChatRoomListView,
    TotalUnreadMessageCountView,
)

app_name = "chat"

urlpatterns = [
    path("total-unread-messages", TotalUnreadMessageCountView.as_view(), name="total-unread-messages"),
    path("chatrooms/<uuid:study_group_uuid>/messages", ChatMessageListView.as_view(), name="message-list"),
    path("chatrooms", ChatRoomListView.as_view(), name="room-list"),
]
