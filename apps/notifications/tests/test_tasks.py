from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.notifications import tasks


# 비즈니스 함수로 delay메서드 호출 방식 test
def recruitment_create() -> None:
    recruitment_id = 2
    receiver_id = 3
    tasks.create_recruitment_applicant_task.delay(recruitment_id, receiver_id)


def recruitment_applications_approval() -> None:
    recruitment_id = 1
    applicant_id = 1
    status = "approval"
    tasks.create_recruitment_application_approval_task.delay(recruitment_id, applicant_id, status)


def recruitment_applications_rejection() -> None:
    recruitment_id = 1
    applicant_id = 1
    status = "rejection"
    tasks.create_recruitment_application_rejection_task.delay(recruitment_id, applicant_id, status)


def study_group_join() -> None:
    group_members_id = 1
    new_member_nickname = "테스트유저"
    tasks.create_studygroup_join_task.delay(group_members_id, new_member_nickname)


def study_group_reviewrequest() -> None:
    study_group_id = 1
    group_members_id = 1
    tasks.create_studygroup_reviewrequest_task.delay(study_group_id, group_members_id)


def study_record() -> None:
    group_members_id = 1
    study_notes_id = 1
    author_nickname = "기록작성자"
    tasks.create_study_record_task.delay(group_members_id, study_notes_id, author_nickname)


class CeleryTasksTest(TestCase):

    @patch("apps.notifications.tasks.create_recruitment_application_approval_task.delay")
    def test_create_recruitment_application_approval_task_delay(self, mock_delay: MagicMock) -> None:
        """공고 지원 승인 알림 task delay 테스트"""
        recruitment_applications_approval()
        mock_delay.assert_called_once_with(1, 1, "approval")

    def test_create_recruitment_application_approval_task_execution(self) -> None:
        """공고 지원 승인 알림 task 실행 테스트"""
        try:
            result = tasks.create_recruitment_application_approval_task(1, 1, "approval")

            self.assertIn("user_id", result)
            self.assertEqual(result["user_id"], 1)
            self.assertEqual(result["type"], "APPLICATION_APPROVAL")
            self.assertIn("content", result)
            self.assertIn("승인되었습니다", result["content"])
        except Exception as e:
            self.fail(f"recruitment_application_approval() 함수 실행 실패:{e}")

    @patch("apps.notifications.tasks.create_recruitment_application_rejection_task.delay")
    def test_create_recruitment_application_rejection_task_delay(self, mock_delay: MagicMock) -> None:
        """공고 지원 거절 알림 task delay 테스트"""
        recruitment_applications_rejection()
        mock_delay.assert_called_once_with(1, 1, "rejection")

    def test_create_recruitment_application_rejection_task_execution(self) -> None:
        """공고 지원 거절 알림 task 실행 테스트"""
        try:
            result = tasks.create_recruitment_application_rejection_task(1, 1, "rejection")

            self.assertIn("user_id", result)
            self.assertEqual(result["user_id"], 1)
            self.assertEqual(result["type"], "APPLICATION_REJECTION")
            self.assertIn("content", result)
            self.assertIn("거절되었습니다", result["content"])

        except Exception as e:
            self.fail(f"recruitment_application_rejection() 함수 실행 실패:{e}")

    @patch("apps.notifications.tasks.create_studygroup_join_task.delay")
    def test_create_studygroup_join_task_delay(self, mock_delay: MagicMock) -> None:
        """스터디 그룹 참여 알림 task delay 테스트"""
        study_group_join()
        mock_delay.assert_called_once_with(1, "테스트유저")

    def test_create_studygroup_join_task_execution(self) -> None:
        """스터디 그룹 참여 알림 task 실행 테스트"""
        try:
            result = tasks.create_studygroup_join_task(1, "테스트유저")

            self.assertIn("user_id", result)
            self.assertEqual(result["user_id"], 1)
            self.assertEqual(result["type"], "STUDY_GROUP_JOIN")
            self.assertIn("content", result)
            self.assertIn("테스트유저", result["content"])
            self.assertIn("참여했습니다", result["content"])

        except Exception as e:
            self.fail(f"studygroup_join() 함수 실행 실패:{e}")

    @patch("apps.notifications.tasks.create_studygroup_reviewrequest_task.delay")
    def test_create_studygroup_reviewrequest_task_delay(self, mock_delay: MagicMock) -> None:
        """스터디 그룹 후기 요청 알림 task delay 테스트"""
        study_group_reviewrequest()
        mock_delay.assert_called_once_with(1, 1)

    def test_create_studygroup_reviewrequest_task_execution(self) -> None:
        """스터디 그룹 후기 요청 알림 task 실행 테스트"""
        try:
            result = tasks.create_studygroup_reviewrequest_task(1, 1)

            self.assertIn("user_id", result)
            self.assertEqual(result["user_id"], 1)
            self.assertEqual(result["type"], "STUDY_REVIEW_REQUEST")
            self.assertIn("content", result)
            self.assertIn("후기", result["content"])
        except Exception as e:
            self.fail(f"studygroup_reviewrequest() 함수 실행 실패:{e}")

    @patch("apps.notifications.tasks.create_study_record_task.delay")
    def test_create_study_record_task_delay(self, mock_delay: MagicMock) -> None:
        """스터디 기록 작성 알림 task delay 테스트"""
        study_record()
        mock_delay.assert_called_once_with(1, 1, "기록작성자")

    def test_create_study_record_task_execution(self) -> None:
        """스터디 기록 작성 알림 task 실행 테스트"""
        try:
            result = tasks.create_study_record_task(1, 1, "기록작성자")

            self.assertIn("user_id", result)
            self.assertEqual(result["user_id"], 1)
            self.assertEqual(result["type"], "STUDY_RECORD_CREATED")
            self.assertIn("content", result)
            self.assertIn("기록작성자", result["content"])
            self.assertIn("스터디 기록", result["content"])
        except Exception as e:
            self.fail(f"study_record() 함수 실행 실패:{e}")
