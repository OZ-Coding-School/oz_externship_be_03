import string
import uuid
from typing import Final


class Base62:
    BASE: Final[str] = string.ascii_letters + string.digits
    BASE_LEN: Final[int] = len(BASE)

    @classmethod
    def encode(cls, num: int) -> str:
        if num < 0:
            raise ValueError(f"{cls}.encode() needs positive integer but you passed: {num}")

        if num == 0:
            return cls.BASE[0]

        result = []

        while num:
            num, remainder = divmod(num, cls.BASE_LEN)
            result.append(cls.BASE[remainder])

        return "".join(result)

    @classmethod
    def uuid_encode(cls, u: uuid.UUID, length: int = 6) -> str:
        """
        UUID 객체를 Base62 문자열로 변환

        Args:
            u (uuid.UUID): 변환할 UUID 객체

        Returns:
            str: Base62로 인코딩된 문자열
        """
        return cls.encode(u.int)[:length]
