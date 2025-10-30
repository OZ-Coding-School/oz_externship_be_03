from django.urls import path

from apps.recruitments.views.search_log import SearchLogAPIView

urlpatterns = [
    path("", SearchLogAPIView.as_view(), name="search-log-list-create"),
]
