from __future__ import annotations

from typing import Any

from django.http import HttpRequest
from typing import Any

from django.views import View
from rest_framework.permissions import BasePermission, DjangoObjectPermissions
from rest_framework.request import Request

from apps.studies.models.groups import GroupMember, StudyGroup

from apps.studies.models import StudyNote


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


class IsGroupMember(BasePermission):
    """
    임시 퍼미션 예시
    - POST: 그룹 멤버만
    - GET: 그룹 멤버 or 인증된 유저 (공개 접근 허용 가능)
    - PUT/DELETE: 그룹 멤버이면서 작성자만
    """

    message = "해당 노트에 대한 접근 권한이 없습니다."

    def has_object_permission(self, request: Request, view: View, obj: Any) -> bool:
        user = request.user

        # 인증되지 않은 경우 읽기(GET)만 허용
        if not user.is_authenticated:
            return request.method == "GET"

        # 대상 객체가 StudyNote가 아닐 경우 기본 False
        if not isinstance(obj, StudyNote):
            return False

        group = obj.study_group
        if group is None:
            return False

        is_member = group.members.filter(user=user).exists()
        is_author = getattr(obj, "author", None) == user

        # HTTP 메서드별 접근 제어
        if request.method == "GET":
            return is_member or user.is_authenticated

        elif request.method == "POST":
            return is_member

        elif request.method in ("PUT", "PATCH", "DELETE"):
            return is_member and is_author

        return False

    def has_permission(self, request: Request, view: View) -> bool:
        """
        단순 인증 여부 선필터
        """
        # 조회(GET)는 비로그인 허용
        if request.method == "GET":
            return True
        return request.user.is_authenticated
