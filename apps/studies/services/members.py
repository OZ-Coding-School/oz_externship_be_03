from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.db import transaction

from apps.studies.models.groups import GroupMember, StudyGroup


class MemberService:
    """REQ-STDY-006~008: 스터디 멤버 관련 서비스 로직"""

    @staticmethod
    @transaction.atomic
    def kick_member(study_group: StudyGroup, member_id: int) -> None:
        """
        REQ-STDY-006: 리더가 특정 멤버를 추방.
        - 대상 멤버가 그룹에 속하지 않으면 예외 발생
        - 리더 자신은 추방할 수 없음
        """
        try:
            target_member = GroupMember.objects.get(id=member_id, study_group=study_group)
        except ObjectDoesNotExist:
            raise PermissionDenied("요청한 사용자를 스터디 그룹에서 찾을 수 없습니다.")

        if target_member.is_leader:
            raise PermissionDenied("리더는 추방할 수 없습니다.")

        target_member.delete()

    @staticmethod
    @transaction.atomic
    def leave_group(study_group: StudyGroup, user_id: int) -> None:
        """
        REQ-STDY-007: 사용자가 스스로 그룹에서 탈퇴.
        - 리더는 탈퇴 불가 (위임 후 가능)
        """
        try:
            member = GroupMember.objects.get(study_group=study_group, user_id=user_id)
        except ObjectDoesNotExist:
            raise PermissionDenied("해당 사용자는 스터디 그룹의 멤버가 아닙니다.")

        if member.is_leader:
            raise PermissionDenied("리더는 탈퇴할 수 없습니다. 먼저 리더 권한을 위임하세요.")

        member.delete()

    @staticmethod
    @transaction.atomic
    def delegate_leader(study_group: StudyGroup, target_member_id: int) -> None:
        """
        REQ-STDY-008: 리더 권한을 다른 멤버에게 위임.
        - 자기 자신에게 위임 시 예외
        - 리더/멤버 상태 교체
        """
        try:
            current_leader = GroupMember.objects.get(study_group=study_group, is_leader=True)
        except ObjectDoesNotExist:
            raise PermissionDenied("현재 리더를 찾을 수 없습니다.")

        try:
            new_leader = GroupMember.objects.get(id=target_member_id, study_group=study_group)
        except ObjectDoesNotExist:
            raise PermissionDenied("위임 대상 멤버를 찾을 수 없습니다.")

        if current_leader.id == new_leader.id:
            raise PermissionDenied("자기 자신에게 리더를 위임할 수 없습니다.")

        # 리더 교체
        current_leader.is_leader = False
        new_leader.is_leader = True
        current_leader.save(update_fields=["is_leader"])
        new_leader.save(update_fields=["is_leader"])
