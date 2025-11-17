from apps.users.validators import validate_korean_phone


def normalize_kr_phone(raw: str) -> str:
    """
    입력: '010XXXXXXXX' (validate_korean_phone로 검증)
    출력: '+8210XXXXXXXX' (E.164)
    """
    validate_korean_phone(raw)
    return f"+82{raw[1:]}"


def denormalize_kr_phone(e164: str) -> str:
    """
    입력: '+8210XXXXXXXX' (E.164)
    출력: '010XXXXXXXX' (국내 표준 형식)
    """
    if not e164.startswith("+82"):
        raise ValueError("E.164 형식이 아닙니다. '+82'로 시작해야 합니다.")

    # +82 다음의 번호를 국내 형식으로 변환
    local = e164[3:]
    if not local.startswith("10"):
        raise ValueError("한국 휴대폰 번호 형식(+8210...)이 아닙니다.")

    return f"0{local}"
