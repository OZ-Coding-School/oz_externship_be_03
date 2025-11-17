from apps.studies.urls.groups import urlpatterns as groups_urlpatterns
from apps.studies.urls.members import urlpatterns as members_urlpatterns
from apps.studies.urls.notes import urlpatterns as notes_urlpatterns
from apps.studies.urls.reviews import urlpatterns as reviews_urlpatterns
from apps.studies.urls.schedules import urlpatterns as schedules_urlpatterns

app_name = "studies"

urlpatterns = [
    *groups_urlpatterns,
    *members_urlpatterns,
    *notes_urlpatterns,
    *reviews_urlpatterns,
    *schedules_urlpatterns,
]
