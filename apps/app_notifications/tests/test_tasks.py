from unittest.mock import patch
from django.test import TestCase
from apps.app_notifications import tasks

# 비즈니스 함수로 delay메서드 호출 방식 test
def recruitment_create():
    recruitment_id = 2
    receiver_id = 3
    tasks.create_recruitment_applicant_task.delay(recruitment_id, receiver_id)

class CeleryTasksTest(TestCase):

    @patch('apps.app_notifications.tasks.create_recruitment_applicant_task.delay')
    def test_create_recruitment_applicant_task_delay(self,mock_delay):
        ''' 공고 지원 알림 task delay 테스트'''

        # When
        recruitment_create()
        # Then
        mock_delay.assert_called_once_with(2,3)

    def  test_create_recruitment_applicant_task_execution(self):
        ''' 공고 지원 알림 task 실행 테스트'''
        #When & Then
        try:
            recruitment_create()

            self.assertTrue(True)
        except Exception as e:
            self.fail(f"recruitment_create() 함수 실행 실패:{e}")


