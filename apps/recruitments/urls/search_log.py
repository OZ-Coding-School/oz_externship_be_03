from django.urls import path

from apps.recruitments.views.search_log import SearchLogListCreateAPIView

urlpatterns = [
    path("search-logs/", SearchLogListCreateAPIView.as_view(), name="searchlog-list-create"),
]
