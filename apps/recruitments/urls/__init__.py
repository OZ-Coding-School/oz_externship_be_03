from django.urls import include, path

from .bookmark import urlpatterns as bookmark_urls
from .recruitments import urlpatterns as recruitment_urls

# 충돌 방지를 위해 prefix 구분
urlpatterns = [
    path("recruitments/", include(recruitment_urls)),
    path("bookmarks/", include(bookmark_urls)),
]
