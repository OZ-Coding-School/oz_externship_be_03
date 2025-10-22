import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from profanity_check import predict_prob  # type: ignore[import-untyped]


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
#  5) 금칙어(운영자/관리자/admin 등)와 욕설 포함 금지
# ------------------------------------------------------------
NICK_RE = re.compile(r"^[A-Za-z0-9가-힣_.]{2,20}$")
RESERVED = {"admin", "administrator", "운영자", "관리자", "root", "system", "moderator", "staff"}
KOR_BANNED_WORDS = {
    "씨발",
    "시발",
    "ㅅㅂ",
    "병신",
    "또라이",
    "개새",
    "개새끼",
    "좆",
    "썅",
    "염병",
    "꺼져",
}
_ASCII_RE = re.compile(r"[A-Za-z]")  # 영어 포함 여부 판단


def _contains_korean_badword(nickname: str) -> bool:
    # 한글 욕설 부분 포함 검사
    low = nickname.lower()
    return any(bad.lower() in low for bad in KOR_BANNED_WORDS)


def _english_profane(nickname: str) -> bool:
    # 영어 욕설 검사
    if not _ASCII_RE.search(nickname):
        return False
    prob = float(predict_prob([nickname])[0])
    return prob >= 0.7


def validate_nickname(nickname: str) -> None:
    try:
        from profanity_check import predict_prob

        _ALT_AVAILABLE = True
    except Exception:
        _ALT_AVAILABLE = False

    """닉네임 유효성 검사"""
    if " " in nickname or nickname.strip() != nickname:
        raise ValidationError("닉네임에 공백은 사용할 수 없습니다.")

    if not NICK_RE.fullmatch(nickname):
        raise ValidationError("닉네임은 2~20자, 한글/영문/숫자/_/. 만 가능합니다.")

    if nickname.isdigit():
        raise ValidationError("숫자만으로는 사용할 수 없습니다.")

    if nickname.lower() in (s.lower() for s in RESERVED):
        raise ValidationError("사용할 수 없는 닉네임입니다.")

    if _contains_korean_badword(nickname) or _english_profane(nickname):
        raise ValidationError("부적절한 단어가 포함되어 사용할 수 없습니다.")


# ------------------------------------------------------------
# 이름 검증기
#  1) 길이 2~30자
#  2) 허용문자: 한글/영문만 (숫자/특수문자/공백 불가)
# ------------------------------------------------------------
_NAME_RE = re.compile(r"^[A-Za-z가-힣]{2,30}$")


def validate_name(name: str) -> None:
    """이름 유효성 검사"""
    if " " in name or name.strip() != name:
        raise ValidationError("이름에 공백은 사용할 수 없습니다.")

    if not _NAME_RE.fullmatch(name):
        raise ValidationError("이름은 2~30자이며 한글/영문만 가능합니다.")
