from __future__ import annotations

import uuid
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpRequest
from rest_framework.permissions import (
    SAFE_METHODS,
    BasePermission,
    DjangoObjectPermissions,
)
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.studies.models import Review
from apps.studies.models.groups import GroupMember, StudyGroup
from apps.studies.models.notes import StudyNote


# 리더 여부 권한 확인
class IsGroupLeader(BasePermission):
    message = "리더만 접근 가능한 기능입니다."

    def has_permission(self, request: Request, view: APIView) -> bool:
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


# 노트 작성시 멤버 검증 (group_uuid)
class IsGroupMember(BasePermission):
    message = "해당 스터디 그룹의 멤버만 접근할 수 있습니다."

    def has_permission(self, request: Request, view: APIView) -> bool:
        if request.method != "POST":
            return True

        user = getattr(request, "user", None)
        if not (user and user.is_authenticated):
            self.message = "로그인이 필요합니다."
            return False

        group_uuid_str = request.data.get("group_uuid")
        if not group_uuid_str or not str(group_uuid_str).strip():
            self.message = "요청 본문에 'group_uuid'가 필요합니다."
            return False

        try:
            group_uuid = uuid.UUID(str(group_uuid_str))
        except Exception:
            self.message = "유효한 group_uuid가 필요합니다."
            return False

        try:
            group = StudyGroup.objects.get(uuid=group_uuid)
        except ObjectDoesNotExist:
            self.message = "해당 그룹이 존재하지 않습니다."
            return False

        if not group.members.filter(user=user).exists():
            self.message = "해당 스터디 그룹의 멤버만 생성할 수 있습니다."
            return False

        setattr(view, "_group", group)  # 시리얼라이저 용 재사용 컨텍스트
        return True

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        if not isinstance(obj, StudyNote):
            return False
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated):
            return False
        group = getattr(obj, "study_group", None)
        if group is None:
            return False
        exists: bool = group.members.filter(user=user).exists()
        return exists


class IsStudyNoteAuthor(BasePermission):
    """
    노트 작성자만 수정/삭제 가능.
    """

    message = "해당 노트를 수정 또는 삭제할 권한이 없습니다."

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        user = request.user

        if not request.user.is_authenticated:
            return False

        # 읽기 메서드는 허용(열람 제약은 IsGroupMember가 담당)
        if request.method in SAFE_METHODS:
            return True

        # 쓰기 메서드는 작성자만 허용
        # (아래 author_id 비교는 FK 컬럼 값이므로 추가 쿼리/역참조 없이 비교안전하다고하여 수정)
        return getattr(obj, "author_id", None) == getattr(request.user, "id", None)


class IsReviewOwner(BasePermission):
    message = "본인이 작성한 리뷰만 수정할 수 있습니다."

    def has_object_permission(
        self,
        request: HttpRequest,
        view: Any,
        obj: Any,
    ) -> bool:
        return (
            bool(request.user)
            and request.user.is_authenticated
            and isinstance(obj, Review)
            and obj.user_id == request.user.id
        )
