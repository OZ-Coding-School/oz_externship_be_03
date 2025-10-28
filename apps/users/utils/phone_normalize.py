from apps.users.validators import validate_korean_phone


def normalize_kr_phone(raw: str) -> str:
    """
    입력: '010XXXXXXXX' (validate_korean_phone로 검증)
    출력: '+8210XXXXXXXX' (E.164)
    """
    validate_korean_phone(raw)
    return f"+82{raw[1:]}"
