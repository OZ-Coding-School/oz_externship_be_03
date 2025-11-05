from rest_framework.exceptions import ValidationError

from apps.recruitments.models.bookmark import Bookmark
from apps.recruitments.models.recruitments import Recruitment
from apps.users.models import User


def create_bookmark(user: User, recruitment_id: int) -> Bookmark:
    try:
        recruitment = Recruitment.objects.get(id=recruitment_id)
    except Recruitment.DoesNotExist:
        raise ValidationError("존재하지 않는 모집글입니다.")

    if Bookmark.objects.filter(user=user, recruitment=recruitment).exists():
        raise ValidationError("이미 북마크한 모집글입니다.")

    bookmark = Bookmark.objects.create(user=user, recruitment=recruitment)
    return bookmark
