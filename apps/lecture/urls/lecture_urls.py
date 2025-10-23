from django.urls import path

from apps.lecture.views import LectureListView, LectureReviewListView

app_name = "lecture"

urlpatterns = [
    path("", LectureListView.as_view(), name="lecture-list"),
    path("<uuid:uuid>/reviews", LectureReviewListView.as_view(), name="lecture-review-list"),
]
