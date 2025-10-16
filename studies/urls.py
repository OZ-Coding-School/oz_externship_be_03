from django.urls import path
from . import views

urlpatterns = [
    path("studies/notes/", views.StudyNoteListCreateView.as_view(), name="study_note_list_create"),
    
    path("studies/notes/<int:note_id>/", views.StudyNoteDetailView.as_view(), name="study_note_detail"),
]
