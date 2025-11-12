from django.urls import path

from apps.studies.views.groups import AdminStudyGroupDetailView, AdminStudyGroupListView
from apps.studies.views.reviews import AdminReviewDetailView, AdminReviewListView

app_name = "admin_studies"

urlpatterns = [
    path(
        "admin/groups",
        AdminStudyGroupListView.as_view(),
        name="admin-study-group-list",
    ),
    path(
        "admin/groups/<uuid:group_uuid>",
        AdminStudyGroupDetailView.as_view(),
        name="admin-study-group-detail",
    ),
    path("admin/reviews", AdminReviewListView.as_view(), name="admin-review-list"),
    path(
        "admin/reviews/<int:review_id>",
        AdminReviewDetailView.as_view(),
        name="admin-review-detail",
    ),
]
