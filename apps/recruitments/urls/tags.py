from django.urls import path

from apps.recruitments.views.tag_views import TagAPIView

urlpatterns = [
    path("/tags", TagAPIView.as_view(), name="tags"),
]
