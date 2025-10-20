from unittest.mock import patch
from django.test import TestCase
from apps.app_notifications import tasks

class CeleryTasksTest(TestCase):

    @patch('apps.app_notifications.tasks.create_recruitment_applicant_task.delay')
    def test_create_recruitment_applicant_task_delay(self,mock_delay):
        ''' 공고 지원 알림 task delay 테스트'''
        #Given
        recruitment_id = 1
        receiver_id = 2
        # When
        tasks.create_recruitment_applicant_task.delay(recruitment_id, receiver_id)
        # Then
        mock_delay.assert_called_with(recruitment_id, receiver_id)

    def  test_create_recruitment_applicant_task_execution(self):
        ''' 공고 지원 알림 task 실행 테스트'''
        #Given
        recruitment_id = 1
        receiver_id = 2

        #When
        result = tasks.create_recruitment_applicant_task(recruitment_id, receiver_id)

        #Then
        self.assertIsInstance(result, dict) # 타입 검사
        self.assertEqual(result["user_id"],receiver_id) # 동등성 검사
        self.assertEqual(result["type"],"APPLICATION_CREATED") # 동등성 검사
        self.assertIn("새로운 지원자가 지원했습니다.",result["content"]) # 포함 되어있는지 확인


