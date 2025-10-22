from apps.studies.models.groups import StudyGroup


# 스터디 그룹 리더 위임 비즈니스 로직
class MemberService:
    @staticmethod
    def delegate_leader(group: StudyGroup, target_user_id: int) -> None:
        MemberService.validate_study_group(study_group=group)
        MemberService.validate_target_user_id(user_id=target_user_id)
        # TODO: 추후 DB 업데이트 로직 추가
        return

    @staticmethod
    def validate_study_group(study_group: StudyGroup):
        if not isinstance(study_group, StudyGroup):
            raise ValueError("유효하지 않은 스터디 그룹입니다.")
    
    @staticmethod
    def validate_target_user_id(user_id: int):
        if user_id <= 0:
            raise ValueError("유효하지 않은 유저 ID입니다.")
