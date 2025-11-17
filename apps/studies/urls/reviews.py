from django.urls import path

from apps.studies.views.reviews import GroupReviewListCreateView, GroupReviewUpdateView

urlpatterns = [
    # 특정 스터디 그룹의 리뷰 목록 조회 및 생성
    path("groups/<uuid:group_uuid>/reviews", GroupReviewListCreateView.as_view(), name="group-reviews"),
    path(
        "groups/<uuid:group_uuid>/reviews/<uuid:review_uuid>",
        GroupReviewUpdateView.as_view(),
        name="group-review-detail",
    ),
]
