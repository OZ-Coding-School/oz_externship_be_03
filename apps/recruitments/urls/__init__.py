from django.urls import include, path

from .bookmark import urlpatterns as bookmark_urls
from .recruitments import urlpatterns as recruitment_urls

urlpatterns = [
    path("recruitments/", include(recruitment_urls)),
    path("bookmarks/", include(bookmark_urls)),
]
