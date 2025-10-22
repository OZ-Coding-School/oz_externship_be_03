from apps.studies.models.groups import StudyGroup


# 스터디 그룹 리더 위임 비즈니스 로직
class MemberService:
    @classmethod
    def kick_member(cls, group: StudyGroup, target_member_id: int) -> None:
        """스터디 그룹 멤버 추방 비즈니스 로직"""
        cls.validate_study_group(study_group=group)
        cls.validate_target_member_id(member_id=target_member_id)
        return

    @classmethod
    def delegate_leader(cls, group: StudyGroup, target_user_id: int) -> None:
        """스터디 그룹 리더 위임 비즈니스 로직"""
        cls.validate_study_group(study_group=group)
        cls.validate_target_user_id(user_id=target_user_id)

    @staticmethod
    def validate_target_member_id(member_id: int) -> None:
        if member_id <= 0:
            raise ValueError("유효하지 않은 멤버 ID입니다.")

    @staticmethod
    def validate_study_group(study_group: StudyGroup) -> None:
        if not isinstance(study_group, StudyGroup):
            raise ValueError("유효하지 않은 스터디 그룹입니다.")

    @staticmethod
    def validate_target_user_id(user_id: int) -> None:
        if user_id <= 0:
            raise ValueError("유효하지 않은 유저 ID입니다.")
