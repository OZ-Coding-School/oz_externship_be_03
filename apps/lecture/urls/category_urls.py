from django.urls import path

from apps.lecture.views.category_views import CategoryListView

url_patterns = [
    path("categories", CategoryListView.as_view(), name="category-list"),
]
