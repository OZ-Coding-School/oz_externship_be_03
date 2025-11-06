from django.urls import path

from apps.recruitments.views.tag import RecruitmentTagListCreateView

urlpatterns = [
    path(
        "recruitments/<int:recruitment_id>/tags",
        RecruitmentTagListCreateView.as_view(),
        name="recruitment-tag-list",
    ),
]
