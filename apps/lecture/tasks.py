# import logging
# from typing import Any, Dict
#
# from celery import Task, shared_task  # type: ignore
#
# from apps.lecture.services.recommendation_service.data_loader import DataLoader
# from apps.lecture.services.recommendation_service.model_trainer import ModelTrainer
#
# logger = logging.getLogger(__name__)
#
#
# @shared_task(bind=True, max_retries=3)  # type: ignore[misc]
# def train_full_model_task(self: Task) -> Dict[str, Any]:
#     """전체 모델 학습 비동기 작업"""
#     try:
#         data_loader = DataLoader()
#         trainer = ModelTrainer(data_loader)
#         success = trainer.train_and_save_full_model()
#
#         if not success:
#             raise Exception("Full training failed")
#
#         return {"status": "success", "message": "Full training completed"}
#     except Exception as e:
#         logger.error(f"[CELERY] Full training failed: {e}")
#         raise self.retry(exc=e, countdown=60)
#
#
# @shared_task(bind=True, max_retries=3)  # type: ignore[misc]
# def train_partial_model_task(self: Task) -> Dict[str, Any]:
#     """증분 학습 비동기 작업"""
#     try:
#         data_loader = DataLoader()
#         trainer = ModelTrainer(data_loader)
#         success = trainer.partial_fit_model_and_save()
#
#         if not success:
#             raise Exception("Partial training failed")
#
#         return {"status": "success", "message": "Partial training completed"}
#     except Exception as e:
#         logger.error(f"[CELERY] Partial training failed: {e}")
#         raise self.retry(exc=e, countdown=30)
