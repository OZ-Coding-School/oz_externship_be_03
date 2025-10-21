from django.urls import path

from apps.chat.views.chat_views import ChatMessageCreateAPIView

urlpatterns = [
    path("study-groups/<int:study_group_id>/messages", ChatMessageCreateAPIView.as_view(), name="chat-message-create"),
]
