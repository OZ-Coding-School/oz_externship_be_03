from apps.lecture.urls.bookmark_urls import urlpatterns as bookmark_urls
from apps.lecture.urls.category_urls import url_patterns as category_urls
from apps.lecture.urls.lecture_urls import urlpatterns as lecture_urls

urlpatterns = [
    *lecture_urls,
    *bookmark_urls,
    *category_urls,
]
