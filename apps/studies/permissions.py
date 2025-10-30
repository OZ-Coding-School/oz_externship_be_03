from __future__ import annotations

from typing import Any

from django.http import HttpRequest
from django.views import View
from rest_framework.permissions import BasePermission, DjangoObjectPermissions
from rest_framework.request import Request

from apps.studies.models.groups import GroupMember, StudyGroup


# 리더 여부 권한 확인
class IsGroupLeader(BasePermission):
    message = "리더만 접근 가능한 기능입니다."

    def has_permission(self, request: Request, view: View) -> bool:
        group = getattr(view, "mock_group", None)
        return bool(request.user and group)


class IsGroupMemberDOP(DjangoObjectPermissions):

    def has_permission(self, request: HttpRequest, view: Any) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request: HttpRequest, view: Any, obj: Any) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        if not isinstance(obj, StudyGroup):
            return False
        return GroupMember.objects.filter(
            study_group=obj,
            user=request.user,
        ).exists()
