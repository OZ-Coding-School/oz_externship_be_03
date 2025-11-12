from apps.recruitments.urls.applications import urlpatterns as application_urlpatterns
from apps.recruitments.urls.bookmark import urlpatterns as bookmark_urlpatterns
from apps.recruitments.urls.recruitment_tags import (
    urlpatterns as recruitment_tags_urlpatterns,
)
from apps.recruitments.urls.recruitments import urlpatterns as recruitment_urlpatterns
from apps.recruitments.urls.tags import urlpatterns as tags_urlpatterns

app_name = "recruitments"

urlpatterns = [
    *recruitment_urlpatterns,
    *bookmark_urlpatterns,
    *recruitment_tags_urlpatterns,
    *tags_urlpatterns,
    *application_urlpatterns,
]
