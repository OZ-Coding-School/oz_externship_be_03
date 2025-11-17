from datetime import date, datetime
from enum import Enum


class StudyGroupStatus(Enum):
    PENDING = "PENDING"
    ONGOING = "ONGOING"
    ENDED = "ENDED"


class StudyGroupService:
    @staticmethod
    def get_status_by_date(start_at: str, end_at: str) -> str:

        # 문자열 → 날짜 객체
        start_date = datetime.strptime(start_at, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_at, "%Y-%m-%d").date()

        # 오늘 날짜
        today = date.today()

        if today < start_date:
            status = StudyGroupStatus.PENDING.value
        elif start_date <= today <= end_date:
            status = StudyGroupStatus.ONGOING.value
        else:
            status = StudyGroupStatus.ENDED.value

        return status
