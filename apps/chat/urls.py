from django.urls import path

from apps.chat.views import ChatMessageListView, ChatRoomListView

app_name = "chat"

urlpatterns = [
    path("study-groups/<int:study_group_id>/messages", ChatMessageListView.as_view(), name="message-list"),
    path("rooms", ChatRoomListView.as_view(), name="room-list"),
]
