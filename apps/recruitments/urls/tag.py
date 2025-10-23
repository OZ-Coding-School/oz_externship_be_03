# apps/recruitments/urls/tag.py
from django.urls import path

from apps.recruitments.views.tag import TagDetailView, TagListView

urlpatterns = [
    path("tags/", TagListView.as_view(), name="tag-list-create"),  # GET, POST
    path("tags/<int:tag_id>/", TagDetailView.as_view(), name="tag-detail"),  # GET, PUT, DELETE
]
