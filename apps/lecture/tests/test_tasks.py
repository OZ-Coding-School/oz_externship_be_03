# from unittest import mock
#
# from celery.result import EagerResult  # type: ignore
# from django.test import override_settings
#
# from apps.core.utils.isolated_cache_testcase import IsolatedRedisTestClient
# from apps.lecture.tasks import train_full_model_task, train_partial_model_task
#
#
# @override_settings(
#     CELERY_TASK_ALWAYS_EAGER=True,
#     CELERY_TASK_EAGER_PROPAGATES=True,
# )
# class ALSTaskTests(IsolatedRedisTestClient):
#     @mock.patch("apps.lecture.tasks.ModelTrainer")
#     @mock.patch("apps.lecture.tasks.DataLoader")
#     def test_train_full_model_task_success(self, mock_data_loader: mock.Mock, mock_trainer: mock.Mock) -> None:
#         """전체 모델 학습 task 성공 테스트"""
#         mock_trainer_instance = mock.Mock()
#         mock_trainer_instance.train_and_save_full_model.return_value = True
#         mock_trainer.return_value = mock_trainer_instance
#
#         result: EagerResult = train_full_model_task.apply()
#
#         self.assertEqual(result.status, "SUCCESS")
#         self.assertIn("status", result.result)
#         self.assertEqual(result.result["status"], "success")
#         mock_data_loader.assert_called_once()
#         mock_trainer.assert_called_once()
#
#     @mock.patch("apps.lecture.tasks.ModelTrainer")
#     @mock.patch("apps.lecture.tasks.DataLoader")
#     def test_train_full_model_task_failure(self, mock_data_loader: mock.Mock, mock_trainer: mock.Mock) -> None:
#         """전체 모델 학습 task 실패 테스트"""
#         mock_trainer_instance = mock.Mock()
#         mock_trainer_instance.train_and_save_full_model.return_value = False
#         mock_trainer.return_value = mock_trainer_instance
#
#         with self.assertRaises(Exception) as context:
#             train_full_model_task.apply()
#
#         self.assertIn("Retry", str(context.exception))
#
#     @mock.patch("apps.lecture.tasks.ModelTrainer")
#     @mock.patch("apps.lecture.tasks.DataLoader")
#     def test_train_partial_model_task_success(self, mock_data_loader: mock.Mock, mock_trainer: mock.Mock) -> None:
#         """partial fit 학습 task 성공 테스트"""
#         mock_trainer_instance = mock.Mock()
#         mock_trainer_instance.partial_fit_model_and_save.return_value = True
#         mock_trainer.return_value = mock_trainer_instance
#
#         result: EagerResult = train_partial_model_task.apply()
#
#         self.assertEqual(result.status, "SUCCESS")
#         self.assertIn("status", result.result)
#
#     @mock.patch("apps.lecture.tasks.ModelTrainer")
#     @mock.patch("apps.lecture.tasks.DataLoader")
#     def test_train_partial_model_task_failure(self, mock_data_loader: mock.Mock, mock_trainer: mock.Mock) -> None:
#         """증분 학습 task 실패 테스트"""
#         mock_trainer_instance = mock.Mock()
#         mock_trainer_instance.partial_fit_model_and_save.return_value = False
#         mock_trainer.return_value = mock_trainer_instance
#
#         with self.assertRaises(Exception) as context:
#             train_partial_model_task.apply()
#
#         self.assertIn("Retry", str(context.exception))
