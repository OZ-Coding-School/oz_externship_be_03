from __future__ import annotations

import uuid
from typing import Any, cast

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
from apps.users.models import User


class SafeDjangoObjectPermissions(DjangoObjectPermissions):
    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False

        if not hasattr(user, "has_perms"):
            # User 모델에 has_perms가 없는 경우 그냥 통과
            return True

        return super().has_permission(request, view)

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False

        if not hasattr(user, "has_perms"):
            return True

        return super().has_object_permission(request, view, obj)


# 리더 여부 권한 확인
class IsGroupLeader(SafeDjangoObjectPermissions):
    """스터디 리더만 접근 가능한 Object-level Permission"""

    message = "스터디 리더만 접근할 수 있습니다."

    # DjangoObjectPermissions 기본 권한 매핑 (옵션)
    perms_map = {
        "GET": ["studies.view_studygroup"],
        "OPTIONS": [],
        "HEAD": [],
        "POST": ["studies.add_studygroup"],
        "PUT": ["studies.change_studygroup"],
        "PATCH": ["studies.change_studygroup"],
        "DELETE": ["studies.delete_studygroup"],
    }

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        """스터디 그룹 객체 단위 접근 권한 검사"""

        user = cast(User, request.user)
        if isinstance(obj, StudyGroup):
            group = obj
        elif hasattr(obj, "study_group"):
            group = getattr(obj, "study_group")
        else:
            return False

        # 사용자가 해당 그룹의 멤버가 아니면 접근 불가 → 403
        is_member = GroupMember.objects.filter(study_group=group, user=user).exists()
        if not is_member:
            return False

        # 멤버이긴 하지만 리더가 아닌 경우
        #     서비스 단에서 ValidationError(400)로 처리하기 위해 True 반환
        is_leader = GroupMember.objects.filter(
            study_group=group,
            user=user,
            is_leader=True,
        ).exists()
        if not is_leader:
            # 이후 view/service 로직에서 이 flag로 세분화된 검증 가능
            request._is_leader = False  # type: ignore[attr-defined]
            return True

        # 리더인 경우 접근 허용
        request._is_leader = True  # type: ignore[attr-defined]
        return True


class IsGroupMemberDOP(SafeDjangoObjectPermissions):

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


class IsGroupMember(SafeDjangoObjectPermissions):
    """스터디 그룹 멤버만 접근 가능한 Object-level Permission"""

    message = "해당 스터디 그룹의 멤버가 아닙니다."
    perms_map = {
        "GET": ["studies.view_studygroup"],
        "OPTIONS": [],
        "HEAD": [],
        "POST": ["studies.add_studygroup"],
        "PUT": ["studies.change_studygroup"],
        "PATCH": ["studies.change_studygroup"],
        "DELETE": ["studies.delete_studygroup"],
    }

    def has_permission(self, request: Request, view: APIView) -> bool:
        group_uuid = (
            view.kwargs.get("group_uuid")
            or getattr(request.data, "get", lambda x, d=None: None)("group_uuid")
            or request.data.get("group_uuid")
            if isinstance(request.data, dict)
            else None
        )

        if group_uuid:
            try:
                group = StudyGroup.objects.get(uuid=group_uuid)
                setattr(view, "_group", group)
            except StudyGroup.DoesNotExist:
                pass

        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        """해당 유저가 스터디 그룹의 멤버인지 검사"""
        user = cast(User, request.user)
        group = getattr(view, "_group", None)

        if group is None:
            if isinstance(obj, StudyGroup):
                group = obj
            elif hasattr(obj, "study_group"):
                group = getattr(obj, "study_group")

        if group is None:
            return False

        setattr(view, "_group", group)
        return GroupMember.objects.filter(study_group=group, user=user).exists()


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
