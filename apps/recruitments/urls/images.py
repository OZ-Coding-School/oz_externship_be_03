from django.urls import path
from apps.recruitments.views.images import (
    ImageListCreateAPIView,
    ImageRetrieveDestroyAPIView,
)

urlpatterns = [
    # 공고별 이미지 목록 및 생성
    path(
        "recruitments/<int:recruitment_id>/images/",
        ImageListCreateAPIView.as_view(),
        name="recruitment-images-list-create",
    ),

    # 이미지 개별 조회 및 삭제
    path(
        "images/<int:image_id>/",
        ImageRetrieveDestroyAPIView.as_view(),
        name="images-retrieve-destroy",
    ),
]