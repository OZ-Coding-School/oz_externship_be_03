from django.urls import path

from apps.lecture.views.admin_views import AdminLectureDetailView, AdminLectureListView

app_name = "admin_lecture"

urlpatterns = [
    path("", AdminLectureListView.as_view(), name="admin-lecture-list"),
    path("/<int:lecture_id>", AdminLectureDetailView.as_view(), name="admin-lecture-detail"),
]
