from django.urls import include, path

urlpatterns = [
    path("recruitments/", include(recruitment_urls)),
    path("bookmarks/", include(bookmark_urls)),
]
