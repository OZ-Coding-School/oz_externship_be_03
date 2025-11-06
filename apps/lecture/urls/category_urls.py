from django.urls import path

from apps.lecture.views.category_views import CategoryListView

urlpatterns = [
    path("/categories", CategoryListView.as_view(), name="category-list"),
]
