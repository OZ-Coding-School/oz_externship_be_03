from typing import cast

from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.studies.models.groups import GroupMember
from apps.users.models import User


class IsGroupMember(BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        study_group_uuid = request.data.get(
            "study_group_uuid", request.parser_context["kwargs"].get("study_group_uuid")
        )

        if study_group_uuid:
            is_group_member = GroupMember.objects.filter(
                user=cast(User, request.user), study_group__uuid=study_group_uuid
            ).exists()
            if not is_group_member:
                raise PermissionDenied("해당 사용자는 스터디 그룹 멤버가 아닙니다.")
            return True

        return False
