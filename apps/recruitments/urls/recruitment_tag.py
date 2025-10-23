from django.urls import path

from apps.recruitments.views.recruitment_tag import RecruitmentTagListView

urlpatterns = [
    path(
        "recruitments/<int:recruitment_id>/tags/", RecruitmentTagListView.as_view(), name="recruitment-tag-list"
    ),  # GET, POST
    path(
        "recruitments/<int:recruitment_id>/tags/<int:tag_id>/",
        RecruitmentTagListView.as_view(),
        name="recruitment-tag-delete",
    ),  # DELETE
]
