import logging
import os
import shutil
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, cast

import implicit  # type: ignore
import joblib  # type: ignore
import numpy as np
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from implicit.als import AlternatingLeastSquares  # type: ignore
from scipy.sparse import coo_matrix, csr_matrix

from apps.lecture.services.recommendation_service.constants import (
    ALS_MODEL_CACHE_KEY,
    ALS_PARAMS,
    ALS_TRAINING_LOCK_KEY,
    L_IDX_TO_ID_CACHE_KEY,
    L_TO_IDX_CACHE_KEY,
    U_TO_IDX_CACHE_KEY,
    USER_ITEMS_MATRIX_CACHE_KEY,
    ALS_Hyperparameters,
)
from apps.lecture.services.recommendation_service.data_loader import (  # 타입 변경
    DataLoader,
    MatrixBundleExtended,
)

logger: logging.Logger = logging.getLogger(__name__)

MODEL_TIMESTAMP_VERSION: str = datetime.utcnow().strftime("v%Y%m%d_%H%M%S")
MODEL_DIR: str = settings.MODEL_STORAGE_PATH
MODEL_BUNDLE_PATH: str = os.path.join(
    MODEL_DIR, f"als_model_bundle_{ALS_PARAMS.factors}f_{MODEL_TIMESTAMP_VERSION}.joblib"
)
MODEL_BACKUP_PATH: str = MODEL_BUNDLE_PATH.replace(".joblib", "_backup.joblib")

ALS_CACHE_KEYS: List[str] = [
    ALS_MODEL_CACHE_KEY,
    U_TO_IDX_CACHE_KEY,
    L_TO_IDX_CACHE_KEY,
    L_IDX_TO_ID_CACHE_KEY,
    USER_ITEMS_MATRIX_CACHE_KEY,
]

# 반환 타입 정의
ModelBundleReturn = Tuple[
    Optional[AlternatingLeastSquares],
    Optional[Dict[int, int]],
    Optional[Dict[int, int]],
    Optional[List[int]],
    Optional[List[int]],
    Optional[csr_matrix],
    Optional[datetime],
]


class ModelTrainer:
    """ALS 모델 학습/저장/로드 및 캐시 동기화, atomic 저장, lock 기반 동시성 보호"""

    def __init__(self, data_loader: DataLoader) -> None:
        self.data_loader: DataLoader = data_loader
        self.params: ALS_Hyperparameters = ALS_PARAMS
        os.makedirs(MODEL_DIR, exist_ok=True)
        logger.info(f"[ALS][LIB] Using implicit library version {implicit.__version__}")

    def _clear_redis_cache(self) -> None:
        """캐시 key 일괄 삭제 (모델 버전 무효화, 동기화)"""
        try:
            cache.delete_many(ALS_CACHE_KEYS)
            logger.info(f"[ALS][MODEL_VERSION] Model updated to {MODEL_TIMESTAMP_VERSION}. Redis cache reset.")
        except Exception as e:
            logger.error(f"[ALS][CACHE] Failed to clear Redis cache: {e}")

    def _safe_dump_model(self, obj: Dict[str, Any]) -> bool:
        """
        joblib atomic 저장, 임시파일 + protocol=4 + "xz" 압축,
        백업, rollback, metadata 로깅, 복구 후 캐시 무효화 재시도
        """
        tmp_path: str = MODEL_BUNDLE_PATH + ".tmp"
        recovery_successful: bool = False

        # 기존 파일 백업
        if os.path.exists(MODEL_BUNDLE_PATH):
            try:
                shutil.copyfile(MODEL_BUNDLE_PATH, MODEL_BACKUP_PATH)
                logger.info("[ALS][BACKUP] Existing model file backed up.")
            except Exception as e:
                logger.error(f"[ALS][BACKUP] Failed to create model backup: {e}")

        try:
            # atomic joblib 저장 및 metadata 로깅
            joblib.dump(obj, tmp_path, compress=("xz", 3), protocol=4)
            os.replace(tmp_path, MODEL_BUNDLE_PATH)
            logger.info("[ALS][SAVE] Model saved atomically.")

            if os.path.exists(MODEL_BACKUP_PATH):
                os.remove(MODEL_BACKUP_PATH)
                if settings.DEBUG:
                    logger.debug("[ALS][BACKUP] Backup file deleted.")

            # 모델 사이즈 및 nnz 기록
            m_size_mb: float = os.path.getsize(MODEL_BUNDLE_PATH) / 1e6
            matrix = obj.get("matrix")
            nnz: Optional[int] = matrix.nnz if matrix is not None and hasattr(matrix, "nnz") else None

            logger.info(f"[ALS][SAVE] Model file size: {m_size_mb:.2f} MB, matrix nnz: {nnz}")

            self._clear_redis_cache()
            return True

        except Exception as e:
            logger.error(f"[ALS][SAVE] Error saving model bundle: {e}", exc_info=True)

            if os.path.exists(MODEL_BACKUP_PATH):
                try:
                    shutil.move(MODEL_BACKUP_PATH, MODEL_BUNDLE_PATH)
                    logger.error("[ALS][RECOVERY] Model save failed. Recovered from backup.")
                    recovery_successful = True
                except Exception as recovery_e:
                    logger.critical(f"[ALS][RECOVERY] CRITICAL: Failed to recover model from backup: {recovery_e}")

            if recovery_successful:
                self._clear_redis_cache()  # 복구 후 캐시 무효화 재시도

            return False

    def load_model_and_mappings(self) -> ModelBundleReturn:
        """모델 번들 파일 로드, 불완전시 모두 None 반환"""
        if not os.path.exists(MODEL_BUNDLE_PATH):
            return None, None, None, None, None, None, None
        try:
            data: Dict[str, Any] = joblib.load(MODEL_BUNDLE_PATH)
            return cast(
                ModelBundleReturn,
                (
                    data.get("model"),
                    data.get("user_to_idx"),
                    data.get("lecture_to_idx"),
                    data.get("users"),
                    data.get("lectures"),
                    data.get("matrix"),
                    data.get("last_trained_at"),
                ),
            )
        except Exception as e:
            logger.error(f"[ALS][TRAIN] Error loading model bundle: {e}", exc_info=True)
            return None, None, None, None, None, None, None

    def train_and_save_full_model(self) -> bool:
        """전체 행렬로 ALS 모델 학습 및 저장, atomic lock 적용"""
        logger.info("[ALS][TRAIN] Full Model Training Started.")
        # data_loader의 반환 타입 변경 (6개 요소)
        matrix_bundle_ext: MatrixBundleExtended = self.data_loader.build_user_item_matrix(
            existing_users=None, last_trained_at=None
        )
        if matrix_bundle_ext is None:
            logger.info("[ALS][TRAIN] No interaction data available. Skipping training.")
            return False

        # 6개 요소 언패킹
        matrix_coo, u_to_i, l_to_i, users, lectures, _ = matrix_bundle_ext
        matrix_csr: csr_matrix = cast(coo_matrix, matrix_coo).tocsr()

        model: AlternatingLeastSquares = AlternatingLeastSquares(
            factors=self.params.factors,
            regularization=self.params.regularization,
            iterations=self.params.iterations,
            calculate_training_loss=self.params.calculate_training_loss,
        )

        model.fit(matrix_csr.T)

        obj: Dict[str, Any] = {
            "model": model,
            "user_to_idx": u_to_i,
            "lecture_to_idx": l_to_i,
            "users": users,
            "lectures": lectures,
            "matrix": matrix_csr,
            "last_trained_at": timezone.now(),
        }

        # Redis Lock 기반 저장
        redis_cache = cast(Any, cache)
        with redis_cache.lock(ALS_TRAINING_LOCK_KEY, timeout=600):
            return self._safe_dump_model(obj)

    def partial_fit_model_and_save(self) -> bool:
        """점진학습: 기존 모델/매핑 기반 신규 행렬 합산, shape 변화시 전체 학습 폴백"""
        logger.info("[ALS][PARTIAL] Partial Model Training Started.")
        model_bundle: ModelBundleReturn = self.load_model_and_mappings()
        (
            model,
            u_to_i,
            l_to_i,
            old_users,
            old_lectures,
            old_matrix_csr,
            last_trained_at,
        ) = model_bundle

        if (
            model is None
            or old_matrix_csr is None
            or u_to_i is None
            or l_to_i is None
            or old_users is None
            or last_trained_at is None
        ):
            logger.warning("[ALS][PARTIAL] Base model not found or incomplete. Falling back to full training.")
            return self.train_and_save_full_model()

        # data_loader의 반환 타입 변경 (6개 요소)
        partial_matrix_bundle_ext: MatrixBundleExtended = self.data_loader.build_user_item_matrix(
            existing_users=old_users, last_trained_at=last_trained_at
        )

        if partial_matrix_bundle_ext is None:
            logger.info("[ALS][PARTIAL] No new interaction data since last training. Skipping partial training.")
            return True

        # 6개 요소 언패킹
        partial_matrix_coo, new_u_to_i, new_l_to_i, updated_users, updated_lectures, is_new_user_added = (
            partial_matrix_bundle_ext
        )
        partial_matrix_csr: csr_matrix = cast(coo_matrix, partial_matrix_coo).tocsr()

        # 신규 사용자 유입 확인
        if is_new_user_added:
            logger.warning(
                f"[ALS][PARTIAL] New user(s) detected since {last_trained_at}. Falling back to full training."
            )
            return self.train_and_save_full_model()

        # 행렬 Shape 검사: 신규 사용자 유입이 없는데도 shape이 달라졌는지 확인 (신규 강의만 유입 가능)
        if partial_matrix_csr.shape[0] != old_matrix_csr.shape[0]:
            logger.error("[ALS][PARTIAL] User shape mismatch despite no new user flag. Falling back to full training.")
            return self.train_and_save_full_model()

        # 신규 강의 유입 시 처리: 행렬 열(Column)은 확장되어야 함
        # old_matrix의 shape을 기준으로 새로운 matrix를 만듦.
        # 기존 user_to_idx, lecture_to_idx, users, lectures 사용

        # 신규 상호작용이 기존 matrix의 shape을 넘어서는지 확인 (신규 강의가 유입되었는지 확인)
        new_lec_count = partial_matrix_csr.shape[1]
        old_lec_count = old_matrix_csr.shape[1]

        # 신규 강의 유입이 없고, 기존 강의 수와 새로운 매핑 강의 수가 일치해야 함
        if new_lec_count != old_lec_count:
            # 신규 강의 유입 시에도 partial fit은 위험하므로 full training으로 폴백하는 것이 안전함.
            # Implicit의 partial_fit은 행렬 shape이 같을 때만 안전함.
            logger.warning(
                "[ALS][PARTIAL] Matrix shape mismatch (New item(s) detected). Falling back to full training."
            )
            return self.train_and_save_full_model()

        # 최종 행렬 합산 (Partial Fit은 shape이 같을 때만 안전하므로, shape 일치 검사를 위에 추가했음)
        updated_matrix_csr: csr_matrix = old_matrix_csr + partial_matrix_csr

        if settings.DEBUG:
            logger.debug(
                f"[ALS][PARTIAL] Matrix size updated from {old_matrix_csr.nnz} to {updated_matrix_csr.nnz} non-zero entries."
            )

        # implicit 버전 호환성에 따라 partial_fit 함수 적용
        try:
            # updated_matrix_csr의 row/col 인덱스는 기존 matrix와 동일해야 함
            model.partial_fit_users(np.arange(updated_matrix_csr.shape[0]), updated_matrix_csr)
            model.partial_fit_items(np.arange(updated_matrix_csr.shape[1]), updated_matrix_csr.T)
        except Exception as e:
            logger.error(f"[ALS][LIB] Implicit partial_fit error: {e}. Falling back to full training.", exc_info=True)
            return self.train_and_save_full_model()

        obj: Dict[str, Any] = {
            "model": model,
            "user_to_idx": u_to_i,
            "lecture_to_idx": l_to_i,
            "users": old_users,
            "lectures": old_lectures,
            "matrix": updated_matrix_csr,
            "last_trained_at": timezone.now(),
        }
        redis_cache = cast(Any, cache)
        with redis_cache.lock(ALS_TRAINING_LOCK_KEY, timeout=600):
            return self._safe_dump_model(obj)
