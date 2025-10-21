from apps.studies.models.groups import StudyGroup


# 스터디 그룹 리더 위임 비즈니스 로직
class MemberService:
    @staticmethod
    def delegate_leader(group: StudyGroup, target_user_id: int) -> None:
        if not isinstance(group, StudyGroup):
            raise ValueError("유효하지 않은 스터디 그룹입니다.")
        if target_user_id <= 0:
            raise ValueError("유효하지 않은 유저 ID입니다.")
        # 현재는 목데이터로 진행하나 추후 db업데이트 로직 추가
        return
