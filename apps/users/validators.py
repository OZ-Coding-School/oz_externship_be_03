import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


# ------------------------------------------------------------
# 휴대폰 번호 검증기
# ------------------------------------------------------------
def validate_korean_phone(value: str) -> None:
    if not re.compile(r"^010\d{8}$").match(value):
        raise ValidationError(_("휴대폰 번호 형식이 올바르지 않습니다. 예) 01012345678"))


# ------------------------------------------------------------
# 닉네임 검증기
#  1) 길이 2~20자
#  2) 허용문자: 한글/영문/숫자/밑줄(_)/마침표(.)
#  3) 공백 금지(앞/뒤/중간)
#  4) 숫자만 구성 금지 (예: "1234")
#  5) 금칙어(운영자/관리자/admin 등) 금지
# ------------------------------------------------------------
NICK_RE = re.compile(r"^[A-Za-z0-9가-힣_.]{2,20}$")
RESERVED = {"admin", "administrator", "운영자", "관리자", "root", "system", "moderator", "staff"}


def validate_nickname(nickname: str) -> None:
    """닉네임 유효성 검사"""
    if " " in nickname or nickname.strip() != nickname:
        raise ValidationError("닉네임에 공백은 사용할 수 없습니다.")

    if not NICK_RE.fullmatch(nickname):
        raise ValidationError("닉네임은 2~20자, 한글/영문/숫자/_/. 만 가능합니다.")

    if nickname.isdigit():
        raise ValidationError("숫자만으로는 사용할 수 없습니다.")

    if nickname.lower() in (s.lower() for s in RESERVED):
        raise ValidationError("사용할 수 없는 닉네임입니다.")
