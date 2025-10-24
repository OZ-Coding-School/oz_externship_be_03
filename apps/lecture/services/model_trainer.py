import logging
import os
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta

import joblib  # type: ignore
import numpy as np
from django.conf import settings

logger = logging.getLogger(__name__)

# 자동 분기 - GPU/CPU
try:
    import implicit.gpu.als as implicit_als  # type: ignore

    # GPU 초기화 시도해보고 문제 시 CPU 버전 사용
    try:
        AlternatingLeastSquares = implicit_als.AlternatingLeastSquares
        # 모델 초기화 시도하여 CUDA 확장 유무 확인
        _ = AlternatingLeastSquares(factors=10)
        logger.info("Using GPU ALS")
    except Exception:
        import implicit.als as implicit_als

        AlternatingLeastSquares = implicit_als.AlternatingLeastSquares
        logger.warning("GPU ALS init failed, fallback to CPU ALS")
except ImportError:
    import implicit.als as implicit_als  # type: ignore

    AlternatingLeastSquares = implicit_als.AlternatingLeastSquares
    logger.warning("Using CPU ALS (implicit.gpu.als not found)")


from apps.lecture.services.constants import ALS_PARAMS
from apps.lecture.services.data_loader import DataLoader

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

        model = AlternatingLeastSquares(
            factors=self.params.factors,
            regularization=self.params.regularization,
            iterations=self.params.iterations,
            calculate_training_loss=self.params.calculate_training_loss,
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
        """
        logger.info("--- Partial Model Training Started ---")

        # 1. 기존 모델과 매핑 로드
        model, u_to_i, l_to_i, users, lectures = self.load_model_and_mappings()

        if model is None or u_to_i is None or l_to_i is None or users is None or lectures is None:
            logger.error("Existing model or mappings not found. Cannot perform partial fit.")
            # 점진적 학습은 기존 모델 기반이므로, 모델이 없으면 전체 학습을 먼저 수행해야 함.
            return False

        # 2. 점진적 학습용 데이터 로드 및 행렬 생성
        time_cutoff = datetime.now() - since

        # DataLoader를 사용하여 최근 상호작용만 로드하고 기존 맵을 이용해 행렬 생성
        partial_matrix = self.data_loader.build_partial_user_item_matrix(
            since=time_cutoff,
            u_to_idx=u_to_i,
            l_to_idx=l_to_i
        )

        if partial_matrix is None:
            logger.info(f"No new interaction data found since {time_cutoff}. Skipping partial fit.")
            return True # 학습할 데이터가 없으므로 성공으로 간주

        # 3. 점진적 학습 수행 (CSR 형식의 전치 행렬 요구)
        model.fit_partial(partial_matrix.T.tocsr())

        # 4. 모델 저장 (매핑은 그대로 재사용)
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