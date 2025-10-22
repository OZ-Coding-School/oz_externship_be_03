from django.test import TestCase
from django.contrib.auth import get_user_model
from django_redis import get_redis_connection #type: ignore

from apps.notifications.tasks import create_recruitment_applicant_task

User = get_user_model()

class NotificationTaskTests(TestCase):
    def setUp(self) -> None:
        self.user= User.objects.create(
            nickname="testuser",
            name='testuser',
            phone_number= '01026585695',
            password= 'test123',
            birthday='19950111',
            gender='male'
        )

        redis_client = get_redis_connection('default')
        redis_client.delete(f"notifications:{self.user.id}")

    def test_task_delay_registration(self) -> None:

        result = create_recruitment_applicant_task.delay(1,self.user.id)

        self.assertIsNotNone(result.id)
        self.assertEqual(result.state,'PENDING')