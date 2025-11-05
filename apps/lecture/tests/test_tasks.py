from typing import Any, Dict, cast
from unittest import mock

from celery.exceptions import (  # type: ignore[import-untyped]
    Retry,
    SoftTimeLimitExceeded,
)
from django.test import TestCase, override_settings, tag

from apps.lecture.tasks import partial_fit_model_task, train_full_model_task


class BaseCeleryTaskTests(TestCase):
    """Celery 작업 테스트를 위한 베이스 클래스"""

    success_message: str
    failure_message: str
    EXPECTED_ERROR_LOG_COUNT: int

    def setUp(self) -> None:
        """각 테스트 전에 공통 mock 설정"""
        self.mock_data_loader_patcher = mock.patch("apps.lecture.tasks.DataLoader")
        self.mock_trainer_patcher = mock.patch("apps.lecture.tasks.ModelTrainer")

        self.mock_data_loader = cast(mock.MagicMock, self.mock_data_loader_patcher.start())
        self.mock_trainer = cast(mock.MagicMock, self.mock_trainer_patcher.start())
        self.mock_trainer_instance = cast(mock.MagicMock, self.mock_trainer.return_value)

        # addCleanup으로 예외 발생 시에도 정리 보장
        self.addCleanup(self.mock_data_loader_patcher.stop)
        self.addCleanup(self.mock_trainer_patcher.stop)

    def _assert_trainer_called_correctly(self) -> None:
        """Trainer가 올바르게 호출되었는지 확인하는 헬퍼 메서드"""
        self.mock_data_loader.assert_called_once()
        self.mock_trainer.assert_called_once_with(self.mock_data_loader.return_value)


@tag("celery", "tasks")
@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class TrainFullModelTaskTests(BaseCeleryTaskTests):
    """train_full_model_task Celery 작업 테스트"""

    @classmethod
    def setUpClass(cls) -> None:
        """클래스 레벨 설정"""
        super().setUpClass()
        cls.success_message = "Full model training completed"
        cls.failure_message = "Model training failed"
        cls.EXPECTED_ERROR_LOG_COUNT = 1

    def test_train_full_model_success(self) -> None:
        """ModelTrainer.train_and_save_full_model()이 True 반환 시 성공 메시지와 작업 완료"""
        # Given: 학습이 성공하도록 mock 설정
        self.mock_trainer_instance.train_and_save_full_model.return_value = True

        # When: 작업 실행
        result: Dict[str, Any] = train_full_model_task()

        # Then: 성공 결과 반환 및 메서드 호출 확인
        self.assertEqual(result, {"status": "success", "message": self.success_message})
        self._assert_trainer_called_correctly()
        self.mock_trainer_instance.train_and_save_full_model.assert_called_once()

    def test_train_full_model_failure(self) -> None:
        """ModelTrainer.train_and_save_full_model()이 False 반환 시 예외 발생, 재시도"""
        # Given: 학습이 실패하도록 mock 설정
        self.mock_trainer_instance.train_and_save_full_model.return_value = False

        # When/Then: 원래 예외가 발생하는지 확인
        with self.assertRaisesMessage(Exception, self.failure_message):
            train_full_model_task()

    def test_train_full_model_soft_timeout(self) -> None:
        """SoftTimeLimitExceeded 예외 발생 시 재시도"""
        # Given: SoftTimeLimitExceeded 예외 발생하도록 설정
        self.mock_trainer_instance.train_and_save_full_model.side_effect = SoftTimeLimitExceeded()

        # When/Then: SoftTimeLimitExceeded 예외가 발생하는지 확인
        with self.assertRaises(SoftTimeLimitExceeded):
            train_full_model_task()

    def test_train_full_model_exception_logging(self) -> None:
        """예외 발생 시 에러 로그 기록"""
        # Given: 예외 발생하도록 설정
        self.mock_trainer_instance.train_and_save_full_model.side_effect = Exception("Training error")

        # When/Then: 로깅 및 예외 발생 확인
        with self.assertLogs("apps.lecture.tasks", level="ERROR") as cm:
            with self.assertRaises(Exception):
                train_full_model_task()

                # 로그 메시지 확인 - 더 견고한 검증
        log_messages = [record.getMessage() for record in cm.records]
        self.assertTrue(
            any("Training failed" in msg and "Training error" in msg for msg in log_messages),
            f"Expected error log not found in: {log_messages}",
        )

    def test_train_full_model_retry_with_mock(self) -> None:
        """학습 실패 시 retry 메서드 호출"""
        # Given: 실패하도록 설정
        self.mock_trainer_instance.train_and_save_full_model.return_value = False

        # When/Then: retry 메서드 호출 확인
        with mock.patch.object(train_full_model_task, "retry", side_effect=Retry()) as mock_retry:
            with self.assertRaises(Retry):
                train_full_model_task()
            mock_retry.assert_called_once()


@tag("celery", "tasks")
@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class PartialFitModelTaskTests(BaseCeleryTaskTests):
    """partial_fit_model_task Celery 작업 테스트"""

    @classmethod
    def setUpClass(cls) -> None:
        """클래스 레벨 설정"""
        super().setUpClass()
        cls.success_message = "Partial fit completed"
        cls.failure_message = "Partial fit failed"
        cls.EXPECTED_ERROR_LOG_COUNT = 1

    def test_partial_fit_success(self) -> None:
        """ModelTrainer.partial_fit_model_and_save()가 True 반환 시 성공 메세지, 작업 완료"""
        # Given: 학습이 성공하도록 mock 설정
        self.mock_trainer_instance.partial_fit_model_and_save.return_value = True

        # When: 작업 실행
        result: Dict[str, Any] = partial_fit_model_task()

        # Then: 성공 결과 반환 및 메서드 호출 확인
        self.assertEqual(result, {"status": "success", "message": self.success_message})
        self._assert_trainer_called_correctly()
        self.mock_trainer_instance.partial_fit_model_and_save.assert_called_once()

    def test_partial_fit_failure(self) -> None:
        """ModelTrainer.partial_fit_model_and_save()가 False 반환 시 예외 발생, 재시도"""
        # Given: 학습이 실패하도록 mock 설정
        self.mock_trainer_instance.partial_fit_model_and_save.return_value = False

        # When/Then: 원래 예외가 발생하는지 확인
        with self.assertRaisesMessage(Exception, self.failure_message):
            partial_fit_model_task()

    def test_partial_fit_soft_timeout(self) -> None:
        """SoftTimeLimitExceeded 예외 발생 시 재시도"""
        # Given: SoftTimeLimitExceeded 예외 발생하도록 설정
        self.mock_trainer_instance.partial_fit_model_and_save.side_effect = SoftTimeLimitExceeded()

        # When/Then: SoftTimeLimitExceeded 예외가 발생하는지 확인
        with self.assertRaises(SoftTimeLimitExceeded):
            partial_fit_model_task()

    def test_partial_fit_exception_logging(self) -> None:
        """예외 발생 시 에러 로그 기록"""
        # Given: 예외 발생하도록 설정
        self.mock_trainer_instance.partial_fit_model_and_save.side_effect = Exception("Partial fit error")

        # When/Then: 로깅 및 예외 발생 확인
        with self.assertLogs("apps.lecture.tasks", level="ERROR") as cm:
            with self.assertRaises(Exception):
                partial_fit_model_task()

        # 로그 메시지 확인
        log_messages = [record.getMessage() for record in cm.records]
        self.assertTrue(
            any("Partial fit failed" in msg and "Partial fit error" in msg for msg in log_messages),
            f"Expected error log not found in: {log_messages}",
        )

    def test_partial_fit_retry_with_mock(self) -> None:
        """학습 실패 시 retry 올바르게 호출."""
        # Given: 실패하도록 설정
        self.mock_trainer_instance.partial_fit_model_and_save.return_value = False

        # When/Then: retry 메서드가 호출되는지 확인
        with mock.patch.object(partial_fit_model_task, "retry", side_effect=Retry()) as mock_retry:
            with self.assertRaises(Retry):
                partial_fit_model_task()
            mock_retry.assert_called_once()
