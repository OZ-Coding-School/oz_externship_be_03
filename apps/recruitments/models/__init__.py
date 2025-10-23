from .application import ApplicationStatus
from .attachment import RecruitmentAttachment
from .bookmark import Bookmark
from .recruitment_images import RecruitmentImage
from .recruitment_tag import RecruitmentTag
from .recruitments import Recruitment
from .search_log import SearchLog
from .tag import Tag

__all__ = [
    "ApplicationStatus",
    "RecruitmentAttachment",
    "Bookmark",
    "RecruitmentImage",
    "RecruitmentTag",
    "Recruitment",
    "SearchLog",
    "Tag",
]


def recruitment() -> None:
    """중복된 함수 정의 제거 및 타입 명시."""
    return None
