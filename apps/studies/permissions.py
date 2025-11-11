from __future__ import annotations

from typing import Any, cast

from django.http import HttpRequest
from rest_framework.permissions import (
    BasePermission,
    DjangoObjectPermissions,
)
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.studies.models import Review
from apps.studies.models.groups import StudyGroup
from apps.studies.models.notes import StudyNote
from apps.users.models import User


# 리더 여부 권한 확인
class IsGroupLeader(DjangoObjectPermissions):
    message = "스터디 리더만 접근할 수 있습니다."

    def has_permission(self, request: Request, view: APIView) -> bool:
        return True

    def has_object_permission(self, request: Request, view: APIView, obj: StudyGroup) -> bool:
        if hasattr(obj, "group_members"):
            user = cast(User, request.user)
            return obj.group_members.filter(user=user, is_leader=True).exists()
        return False


class IsGroupMember(DjangoObjectPermissions):
    message = "스터디 그룹 멤버만 접근할 수 있습니다."

    def has_permission(self, request: Request, view: APIView) -> bool:
        return True

    def has_object_permission(self, request: HttpRequest, view: Any, obj: StudyGroup) -> bool:
        user = cast(User, request.user)

        if hasattr(obj, "group_members"):
            return obj.group_members.filter(user=user).exists()

        return False


class IsStudyNoteAuthor(BasePermission):
    message = "해당 노트를 수정 또는 삭제할 권한이 없습니다."

    def has_permission(self, request: Request, view: APIView) -> bool:
        return True

    def has_object_permission(self, request: Request, view: APIView, obj: StudyNote) -> bool:
        return obj.author == request.user


class IsReviewOwner(BasePermission):
    message = "본인이 작성한 리뷰만 수정할 수 있습니다."

    def has_permission(self, request: Request, view: APIView) -> bool:
        return True

    def has_object_permission(self, request: HttpRequest, view: Any, obj: Review) -> bool:
        return obj.user == request.user
