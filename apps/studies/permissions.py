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
    스터디 그룹 멤버만 접근 가능.
    - 인증되지 않은 사용자는 어떤 요청도 불가.
    - 그룹 멤버가 아니면 접근 불가.
    """

    message = "해당 스터디 그룹의 멤버만 접근할 수 있습니다."

    # 로그인 디폴트에서 그룹 멤버 여부
    def has_object_permission(self, request: Request, view: View, obj: Any) -> bool:
        user = request.user

        if not user.is_authenticated:
            return False

        if not isinstance(obj, StudyNote):
            return False

        group = obj.study_group
        if group is None:
            return False

        return group.members.filter(user=user).exists()


class IsStudyNoteAuthor(BasePermission):
    """
    노트 작성자만 수정/삭제 가능.
    """

    message = "해당 노트를 수정 또는 삭제할 권한이 없습니다."

    def has_object_permission(self, request: Request, view: View, obj: Any) -> bool:
        user = request.user

        if not user.is_authenticated:
            return False

        if not isinstance(obj, StudyNote):
            return False

        # 단일 역할: "작성자 여부만 확인"
        if request.method in ("PUT", "PATCH", "DELETE"):
            return obj.author == user

        return True  # 나머지 요청(GET 등)은 제한하지 않음
