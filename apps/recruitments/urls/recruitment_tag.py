from django.urls import path

from apps.recruitments.views.recruitment_tag import RecruitmentTagListView

urlpatterns = [
    path("<int:recruitment_id>/tags/", RecruitmentTagListView.as_view(), name="recruitments_tags_list"),
    path("<int:recruitment_id>/tags/<int:tag_id>/", RecruitmentTagListView.as_view(), name="recruitments_tags_detail"),
]
