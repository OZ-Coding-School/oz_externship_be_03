from django.views import View
from rest_framework.permissions import BasePermission
from rest_framework.request import Request


# 리더 여부 권한 확인
class IsGroupLeader(BasePermission):
    message = "리더만 접근 가능한 기능입니다."

    def has_permission(self, request: Request, view: View) -> bool:
        group = getattr(view, "mock_group", None)
        return bool(request.user and group)
