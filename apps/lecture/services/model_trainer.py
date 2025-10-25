import logging
import os
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

import joblib  # type: ignore
import numpy as np
from django.conf import settings
from django.utils import timezone
from implicit.als import AlternatingLeastSquares  # type: ignore

from apps.lecture.services.constants import ALS_PARAMS
from apps.lecture.services.data_loader import DataLoader

logger = logging.getLogger(__name__)

MODEL_DIR = settings.MODEL_STORAGE_PATH
MODEL_PATH = os.path.join(MODEL_DIR, "als_model.npz")
MAPPING_PATH = os.path.join(MODEL_DIR, "als_mappings.npz")


class ModelTrainer:
    """Implicit ALS 모델 훈련, 저장 및 로드를 관리."""

    MODEL_DIR = MODEL_DIR
    MODEL_PATH = MODEL_PATH
    MAPPING_PATH = MAPPING_PATH

    def __init__(self, data_loader: DataLoader) -> None:
        self.data_loader = data_loader
        self.params = ALS_PARAMS
        os.makedirs(self.MODEL_DIR, exist_ok=True)

    def train_and_save_full_model(self) -> bool:
        logger.info("--- Full Model Training Started ---")
        matrix, u_to_i, l_to_i, users, lectures = self.data_loader.build_user_item_matrix()

        if matrix is None or u_to_i is None or l_to_i is None or users is None or lectures is None:
            logger.info("No interaction data available. Skipping training.")
            return False

        # 팩토리 함수를 통해 ALS 모델 인스턴스 생성
        model = AlternatingLeastSquares(
            factors=self.params.factors,
            regularization=self.params.regularization,
            iterations=self.params.iterations,
            calculate_training_loss=self.params.calculate_training_loss,
        )

        # GPU 미지원 시 경고 로깅
        # 반환된 모델의 모듈 경로를 확인하여 CPU 모델인지 판단
        if model.__class__.__module__ == "implicit.cpu.als":
            logger.warning(
                "GPU not detected or implicit library installed without CUDA support. "
                "Falling back to CPU training. Consider installing the GPU version for faster training."
            )

        model.fit(matrix.T.tocsr())

        if not self._save_model_and_mappings(model, u_to_i, l_to_i, users, lectures):
            logger.error("--- Full Model Training Failed to Save ---")
            return False

        logger.info("--- Full Model Training Finished and Saved ---")
        return True

    def train_and_save_partial_model(self, since: timedelta) -> bool:
        """
        주어진 기간(timedelta) 이내의 새로운 데이터로 모델을 점진적 학습하고 저장.
        신규 강의(아이템)가 발견되면 전체 재학습을 시도합니다.
        """
        logger.info("--- Partial Model Training Started ---")

        # 1. 기존 모델과 매핑 로드
        model, u_to_i, l_to_i, users, lectures = self.load_model_and_mappings()

        if model is None or u_to_i is None or l_to_i is None or users is None or lectures is None:
            logger.warning("Existing model or mappings not found. Cannot perform partial fit.")
            # 기존 모델이 없으면 전체 학습을 시도
            logger.info("Falling back to full training as no existing model was found.")
            return self.train_and_save_full_model()

        # 2. 점진적 학습용 데이터 로드 및 행렬 생성
        time_cutoff = timezone.now() - since

        # DataLoader는 (사용자 ID 리스트, 행렬, 신규 강의 포함 여부) 튜플 반환.
        partial_user_ids, partial_matrix, new_lecture_found = self.data_loader.build_partial_user_item_matrix(
            since=time_cutoff, u_to_idx=u_to_i, l_to_idx=l_to_i
        )

        # 3. 신규 강의 발견 시 전체 재학습 실행
        if new_lecture_found:
            logger.warning(
                "New lectures found in recent interactions. Triggering full model re-train to incorporate new items."
            )
            # 신규 강의가 발견되면 증분 학습 대신 전체 재학습을 수행
            return self.train_and_save_full_model()

        if partial_matrix is None or partial_user_ids is None:
            logger.info(f"No relevant new interaction data found since {time_cutoff}. Skipping partial fit.")
            return True  # 학습할 데이터가 없으므로 성공으로 간주

        # 4. 점진적 학습 수행 (신규 강의가 없을 때만 실행)
        logger.info(f"Updating factors for {len(partial_user_ids)} users.")

        try:
            model.partial_fit_users(np.array(partial_user_ids), partial_matrix)
        except AttributeError as e:
            logger.error(f"model.partial_fit_users 호출 실패: {e}", exc_info=True)
            logger.error(
                "이는 ALS 모델에 해당 메서드가 없거나, 예상치 못한 버전의 implicit 라이브러리 문제일 수 있습니다."
            )
            return False

        # 5. 모델 저장 (매핑 그대로 재사용)
        if not self._save_model_and_mappings(model, u_to_i, l_to_i, users, lectures):
            logger.error("--- Partial Model Training Failed to Save ---")
            return False

        logger.info("--- Partial Model Training Finished and Saved ---")
        return True

    def _save_model_and_mappings(
        self,
        model: Any,
        u_to_i: Dict[int, int],
        l_to_i: Dict[int, int],
        users: List[int],
        lectures: List[int],
    ) -> bool:
        """모델, 매핑 데이터를 디스크에 저장. 저장 실패 시 False 반환."""
        try:
            # 1. 모델 저장
            joblib.dump(model, self.MODEL_PATH)

            # 2. 매핑 데이터 저장
            np.savez(
                self.MAPPING_PATH,
                user_to_idx=np.array(u_to_i, dtype=object),
                lecture_to_idx=np.array(l_to_i, dtype=object),
                users=np.array(users),
                lectures=np.array(lectures),
            )
            return True  # 저장 성공

        # 저장 실패 시 예외를 잡고 False 반환
        except Exception as e:
            # 디스크 공간 부족, 권한 문제 등 파일 쓰기 오류 처리
            logger.error(f"Error saving ALS model or mappings: {e}", exc_info=True)
            return False

    def load_model_and_mappings(
        self,
    ) -> Tuple[
        Optional[Any],
        Optional[Dict[int, int]],
        Optional[Dict[int, int]],
        Optional[List[int]],
        Optional[List[int]],
    ]:
        if not os.path.exists(self.MODEL_PATH) or not os.path.exists(self.MAPPING_PATH):
            return None, None, None, None, None

        try:
            model = joblib.load(self.MODEL_PATH)
            data = np.load(self.MAPPING_PATH, allow_pickle=True)
            u_to_i: Dict[int, int] = data["user_to_idx"].item()
            l_to_i: Dict[int, int] = data["lecture_to_idx"].item()
            users: List[int] = data["users"].tolist()
            lectures: List[int] = data["lectures"].tolist()
            return model, u_to_i, l_to_i, users, lectures
        except Exception as e:
            logger.error(f"Error loading model or mappings: {e}", exc_info=True)
            return None, None, None, None, None
