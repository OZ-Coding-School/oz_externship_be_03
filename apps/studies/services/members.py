from typing import Any
from uuid import UUID

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.studies.models.groups import GroupMember, StudyGroup


class MemberService:
    """REQ-STDY-006~008: 스터디 멤버 관련 서비스 로직"""

    @staticmethod
    @transaction.atomic
    def kick_member(study_group: StudyGroup, target_member_id: int) -> None:
        """REQ-STDY-006: 리더가 특정 멤버를 추방"""
        try:
            target = GroupMember.objects.get(id=target_member_id, study_group=study_group)
        except ObjectDoesNotExist:
            raise ValidationError("해당 멤버를 찾을 수 없습니다.")

        if target.is_leader:
            raise ValidationError("리더는 스스로를 추방할 수 없습니다.")

        target.delete()

    @staticmethod
    @transaction.atomic
    def leave_group(*, user: Any, study_group: StudyGroup) -> None:
        """REQ-STDY-007: 멤버 자진 탈퇴"""
        try:
            member = GroupMember.objects.get(user=user, study_group=study_group)
        except ObjectDoesNotExist:
            raise PermissionDenied("해당 사용자는 스터디 그룹의 멤버가 아닙니다.")

        if member.is_leader:
            raise ValidationError("리더는 탈퇴할 수 없습니다. 먼저 리더 권한을 위임하세요.")

        member.delete()

    @staticmethod
    @transaction.atomic
    def delegate_leader(study_group: StudyGroup, target_member_uuid: UUID) -> dict[str, Any]:
        """REQ-STDY-008: 리더 권한 위임"""
        try:
            current_leader = GroupMember.objects.get(study_group=study_group, is_leader=True)
        except ObjectDoesNotExist:
            raise ValidationError("현재 리더를 찾을 수 없습니다.")

        try:
            new_leader = GroupMember.objects.get(user__uuid=target_member_uuid, study_group=study_group)
        except ObjectDoesNotExist:
            raise ValidationError("위임 대상 멤버를 찾을 수 없습니다.")

        if current_leader.id == new_leader.id:
            raise ValidationError("자기 자신에게 리더를 위임할 수 없습니다.")

        current_leader.is_leader = False
        new_leader.is_leader = True
        current_leader.save(update_fields=["is_leader"])
        new_leader.save(update_fields=["is_leader"])

        return {
            "previous_leader_id": current_leader.user_id,
            "new_leader_id": new_leader.user_id,
        }
