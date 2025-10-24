import os
from typing import Dict, List, Optional, Tuple, cast

import numpy as np
from django.conf import settings
from implicit.als import AlternatingLeastSquares  # type: ignore

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
        print("--- Full Model Training Started ---")
        matrix, u_to_i, l_to_i, users, lectures = self.data_loader.build_user_item_matrix()

        if matrix is None or u_to_i is None or l_to_i is None or users is None or lectures is None:
            print("No interaction data available. Skipping training.")
            return False

        model = AlternatingLeastSquares(
            factors=self.params.factors,
            regularization=self.params.regularization,
            iterations=self.params.iterations,
            calculate_training_loss=self.params.calculate_training_loss,
            use_gpu=self.params.use_gpu,
        )

        model.fit(matrix.T.tocsr())

        self._save_model_and_mappings(model, u_to_i, l_to_i, users, lectures)
        print("--- Full Model Training Finished and Saved ---")
        return True

    def _save_model_and_mappings(
        self,
        model: AlternatingLeastSquares,
        u_to_i: Dict[int, int],
        l_to_i: Dict[int, int],
        users: List[int],
        lectures: List[int],
    ) -> None:
        model.save(self.MODEL_PATH)
        np.savez(
            self.MAPPING_PATH,
            user_to_idx=np.array(u_to_i, dtype=object),
            lecture_to_idx=np.array(l_to_i, dtype=object),
            users=np.array(users),
            lectures=np.array(lectures),
        )

    def load_model_and_mappings(
        self,
    ) -> Tuple[
        Optional[AlternatingLeastSquares],
        Optional[Dict[int, int]],
        Optional[Dict[int, int]],
        Optional[List[int]],
        Optional[List[int]],
    ]:
        if not os.path.exists(self.MODEL_PATH) or not os.path.exists(self.MAPPING_PATH):
            return None, None, None, None, None

        try:
            model = AlternatingLeastSquares.load(self.MODEL_PATH)
            data = np.load(self.MAPPING_PATH, allow_pickle=True)
            u_to_i: Dict[int, int] = data["user_to_idx"].item()
            l_to_i: Dict[int, int] = data["lecture_to_idx"].item()
            users: List[int] = data["users"].tolist()
            lectures: List[int] = data["lectures"].tolist()

            return model, u_to_i, l_to_i, users, lectures
        except Exception as e:
            print(f"Error loading model or mappings: {e}")
            return None, None, None, None, None
