from django.urls import path

from apps.lecture.views.recommendation_views import RecommendationView

urlpatterns = [
    path("/recommendations", RecommendationView.as_view(), name="recommendations"),
]
