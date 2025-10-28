import logging

from apps.studies.models.groups import StudyGroup

logger = logging.getLogger(__name__)


class MemberService:
    @staticmethod
    def kick_member(study_group: StudyGroup, member_id: int) -> None:
        """스터디 그룹 멤버 추방 로직 (Mock)"""
        logger.info(f"[MemberService] 그룹({study_group.id})에서 멤버({member_id}) 추방")

    @staticmethod
    def leave_group(study_group: StudyGroup, user_id: int) -> None:
        """스터디 그룹 자진 탈퇴 로직 (Mock)"""
        logger.info(f"[MemberService] 그룹({study_group.id})에서 사용자({user_id}) 탈퇴")

    @staticmethod
    def delegate_leader(study_group: StudyGroup, target_user_id: int) -> None:
        """리더 위임 로직 (Mock)"""
        logger.info(f"[MemberService] 그룹({study_group.id}) 리더를 사용자({target_user_id})로 위임")
