import uuid

from django.test import TestCase

from apps.core.utils.base62 import Base62


class TestBase62(TestCase):
    def test_base62_encode(self) -> None:
        self.assertEqual(Base62.encode(1), "b")

    def test_base62_uuid4_encode_with_length(self) -> None:
        self.assertEqual(len(Base62.uuid_encode(u=uuid.uuid4(), length=10)), 10)

    def test_base62_num_lower_than_zero(self) -> None:
        with self.assertRaises(ValueError):
            Base62.encode(-1)

    def test_base62_num_is_zero(self) -> None:
        self.assertEqual(Base62.encode(0), "a")
