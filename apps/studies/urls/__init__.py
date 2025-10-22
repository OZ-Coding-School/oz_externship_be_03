from django.urls import include, path

from .notes import *
from .notes import urlpatterns

urlpatterns = [
    #개인브랜치용 Spec API config 없이 할료고 만들음
    path("", include("apps.studies.urls.specs_notes")),
]

from django.conf import settings

if getattr(settings, "LOCAL_MODE", False):
    print(" LOCAL_MODE=True → 개인 Spec API 활성화")  # 확인용 로그
    urlpatterns += [
        path("", include("apps.studies.urls.specs_notes")),  # 개인 전용 Spec 라우트
    ]