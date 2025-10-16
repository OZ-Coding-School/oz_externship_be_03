import uuid

from django.db import models
from django.test import TestCase

from apps.core.models import TimeStampModel, UUIDTimeStampModel


# 테스트를 위한 임시 모델 정의
class TestTimestampedItem(TimeStampModel):
    name = models.CharField(max_length=100)

    class Meta:
        # 테스트 실행기가 이 모델의 DB 테이블을 생성하도록 app_label을 지정합니다.
        app_label = "core"


class TestUUIDItem(UUIDTimeStampModel):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = "core"


class CoreModelTests(TestCase):
    """
    core 앱의 추상 모델(TimeStampModel, UUIDTimeStampModel)의 동작을 테스트합니다.
    """

    def test_soft_delete_and_restore(self) -> None:
        """
        소프트 삭제(soft-delete) 및 복구 기능이 정상 동작하는지 테스트합니다.
        """
        # Given: 테스트 아이템 생성
        item = TestTimestampedItem.objects.create(name="테스트 아이템")

        # When: 아이템을 소프트 삭제
        item.delete()

        # Then: 기본 매니저(objects)는 아이템을 찾을 수 없어야 합니다.
        self.assertEqual(TestTimestampedItem.objects.count(), 0)
        # all_objects 매니저로는 아이템을 찾을 수 있어야 합니다.
        self.assertEqual(TestTimestampedItem.all_objects.count(), 1)
        # deleted_at 필드가 시간으로 채워져 있어야 합니다.
        item.refresh_from_db()
        self.assertIsNotNone(item.deleted_at)

        # When: 아이템을 복구
        item.restore()

        # Then: 기본 매니저(objects)에서 다시 아이템을 찾을 수 있어야 합니다.
        self.assertEqual(TestTimestampedItem.objects.count(), 1)
        # deleted_at 필드는 None이어야 합니다.
        item.refresh_from_db()
        self.assertIsNone(item.deleted_at)

    def test_uuid_field_auto_creation(self) -> None:
        """
        UUIDTimeStampModel을 상속하는 모델이 생성될 때 UUID가 자동으로 채워지는지 테스트합니다.
        """
        # Given & When: UUID 아이템 생성
        item = TestUUIDItem.objects.create(name="UUID 테스트 아이템")

        # Then: uuid 필드는 None이 아니며, UUID 타입이어야 합니다.
        self.assertIsNotNone(item.uuid)
        self.assertIsInstance(item.uuid, uuid.UUID)

    def test_queryset_filtering(self) -> None:
        """
        기본 매니저와 all_objects 매니저가 삭제된 객체를 올바르게 필터링하는지 테스트합니다.
        """
        # Given: 2개의 아이템을 만들고 하나만 삭제
        item1 = TestTimestampedItem.objects.create(name="아이템 1")
        item2 = TestTimestampedItem.objects.create(name="아이템 2")
        item2.delete()

        # Then: 기본 매니저는 삭제되지 않은 아이템 1개만 반환해야 합니다.
        self.assertEqual(TestTimestampedItem.objects.count(), 1)
        self.assertEqual(TestTimestampedItem.objects.first(), item1)

        # Then: all_objects 매니저는 삭제된 아이템을 포함하여 2개를 모두 반환해야 합니다.
        self.assertEqual(TestTimestampedItem.all_objects.count(), 2)
