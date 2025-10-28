from __future__ import annotations
from django.views import View
from rest_framework.permissions import BasePermission
from rest_framework.request import Request

from typing import Any
from rest_framework.permissions import BasePermission
from django.http import HttpRequest

from apps.studies.models.groups import GroupMember

# 리더 여부 권한 확인
class IsGroupLeader(BasePermission):
    message = "리더만 접근 가능한 기능입니다."

    def has_permission(self, request: Request, view: View) -> bool:
        group = getattr(view, "mock_group", None)
        return bool(request.user and group)


class IsGroupMember(BasePermission):
    message = "이 그룹의 멤버만 접근할 수 있습니다."

    def has_permission(self, request: HttpRequest, view: Any) -> bool:
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False

        group_id = view.kwargs.get("group_id")
        if group_id is None:
            return True

        try:
            gid = int(group_id)
        except (TypeError, ValueError):
            return False

        return GroupMember.objects.filter(
            study_group_id=gid,
            user_id=user.id,
        ).exists()