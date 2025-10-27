from django.urls import path
from apps.recruitments.views.attachment import (
    AttachmentListCreateAPIView,
    AttachmentRetrieveDestroyAPIView,
)

urlpatterns = [
    # 공고별 첨부파일 목록 및 생성
    path(
        "recruitments/<int:recruitment_id>/attachments/",
        AttachmentListCreateAPIView.as_view(),
        name="recruitment-attachments-list-create",
    ),

    # 첨부파일 개별 조회 및 삭제
    path(
        "attachments/<int:attachment_id>/",
        AttachmentRetrieveDestroyAPIView.as_view(),
        name="attachments-retrieve-destroy",
    ),
]