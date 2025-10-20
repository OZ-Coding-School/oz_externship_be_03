from django.urls import path

from apps.lecture.views.recommend_views import UserRecommendedLecturesAPIView

urlpatterns = [
    path("/recommendations", UserRecommendedLecturesAPIView.as_view(), name="user-recommendations"),
]
