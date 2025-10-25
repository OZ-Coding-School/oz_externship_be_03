import logging
import os
import shutil
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, cast

import joblib  # type: ignore
import numpy as np
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from implicit.als import AlternatingLeastSquares  # type: ignore
from scipy.sparse import coo_matrix, csr_matrix

from apps.lecture.services.constants import (
    ALS_MODEL_CACHE_KEY,
    ALS_PARAMS,
    L_IDX_TO_ID_CACHE_KEY,
    L_TO_IDX_CACHE_KEY,
    MODEL_VERSION,
    U_TO_IDX_CACHE_KEY,
    USER_ITEMS_MATRIX_CACHE_KEY,
)
from apps.lecture.services.data_loader import DataLoader, MatrixBundle

logger = logging.getLogger(__name__)

# 파일 경로 및 상수 설정
MODEL_DIR: str = settings.MODEL_STORAGE_PATH
# 모델 번들 파일 경로 (버전 및 하이퍼파라미터 포함)
MODEL_BUNDLE_PATH: str = os.path.join(MODEL_DIR, f"als_model_bundle_{ALS_PARAMS.factors}f_{MODEL_VERSION}.joblib")
# 백업 파일 경로: 저장 실패 시 롤백을 위한 임시 파일
MODEL_BACKUP_PATH: str = MODEL_BUNDLE_PATH.replace(".joblib", "_backup.joblib")

# 모델 캐시 키 목록: 학습 완료 후 무효화 대상
ALS_CACHE_KEYS: List[str] = [
    ALS_MODEL_CACHE_KEY,
    U_TO_IDX_CACHE_KEY,
    L_TO_IDX_CACHE_KEY,
    L_IDX_TO_ID_CACHE_KEY,
    USER_ITEMS_MATRIX_CACHE_KEY,
]

# 모델 번들 로드/반환 타입 정의
ModelBundleReturn = Tuple[
    Optional[AlternatingLeastSquares],
    Optional[Dict[int, int]],  # user_to_idx: 사용자 ID -> 인덱스
    Optional[Dict[int, int]],  # lecture_to_idx: 강의 ID -> 인덱스
    Optional[List[int]],  # users: 모든 사용자 ID 리스트
    Optional[List[int]],  # lectures: 모든 강의 ID 리스트
    Optional[csr_matrix],  # matrix: 최종 상호작용 행렬 (CSR)
    Optional[datetime],  # last_trained_at: 최종 학습 시각
]


class ModelTrainer:
    """ALS 모델 학습, 저장 및 로드 관리 (전체 및 점진적 학습 지원)"""

    def __init__(self, data_loader: DataLoader) -> None:
        """
        ModelTrainer 초기화.

        :param data_loader: 데이터 로드를 위한 DataLoader 인스턴스
        """
        self.data_loader: DataLoader = data_loader
        self.params = ALS_PARAMS
        # 모델 저장 디렉토리 생성 (없으면 생성)
        os.makedirs(MODEL_DIR, exist_ok=True)

    # -- 1. 저장 및 캐시 관리 (Save & Cache Management)

    def _clear_redis_cache(self) -> None:
        """
        모델 저장 성공 후 Redis 캐시를 비워 버전 충돌 및 구버전 모델 사용 방지.
        """
        try:
            cache.delete_many(ALS_CACHE_KEYS)
            logger.info(f"[ALS][MODEL_VERSION] Model updated to {MODEL_VERSION}. Redis cache reset.")
        except Exception as e:
            logger.error(f"[ALS][CACHE] Failed to clear Redis cache: {e}")

    def _safe_dump_model(self, obj: Dict[str, Any]) -> bool:
        """
        모델 파일 백업/복구 로직을 포함한 안전한 모델 저장.

        :param obj: joblib으로 저장할 모델 및 메타데이터 딕셔너리
        :return: 저장 성공 여부
        """

        # 1. 기존 모델 파일 백업
        if os.path.exists(MODEL_BUNDLE_PATH):
            try:
                shutil.copyfile(MODEL_BUNDLE_PATH, MODEL_BACKUP_PATH)
                logger.info("[ALS][BACKUP] Existing model file backed up.")
            except Exception as e:
                logger.error(f"[ALS][BACKUP] Failed to create model backup: {e}")

        # 2. 새 모델 저장 시도
        try:
            # joblib을 사용하여 객체 저장 (압축 레벨 3)
            joblib.dump(obj, MODEL_BUNDLE_PATH, compress=3)
            logger.info("[ALS][SAVE] Model saved successfully.")

            # 3. 저장 성공 시 백업 파일 삭제 및 캐시 정리
            if os.path.exists(MODEL_BACKUP_PATH):
                os.remove(MODEL_BACKUP_PATH)
                if settings.DEBUG:
                    logger.debug("[ALS][BACKUP] Backup file deleted.")

            self._clear_redis_cache()
            return True

        except Exception as e:
            logger.error(f"[ALS][SAVE] Error saving model bundle: {e}", exc_info=True)

            # 4. 저장 실패 시 백업 파일로 롤백 시도
            if os.path.exists(MODEL_BACKUP_PATH):
                try:
                    # 백업 파일로 덮어쓰기
                    shutil.move(MODEL_BACKUP_PATH, MODEL_BUNDLE_PATH)
                    logger.error("[ALS][RECOVERY] Model save failed. Recovered from backup.")
                except Exception as recovery_e:
                    logger.critical(f"[ALS][RECOVERY] CRITICAL: Failed to recover model from backup: {recovery_e}")

            return False

    def load_model_and_mappings(self) -> ModelBundleReturn:
        """
        모델 번들 파일 (joblib)을 로드하여 모델, 매핑, 메타데이터 반환.

        :return: ModelBundleReturn 타입 튜플 (로드 실패 시 모두 None)
        """
        if not os.path.exists(MODEL_BUNDLE_PATH):
            # 파일이 없으면 모두 None 반환
            return None, None, None, None, None, None, None

        try:
            data: Dict[str, Any] = joblib.load(MODEL_BUNDLE_PATH)
            # 타입 캐스팅을 통해 반환 값의 안정성 확보
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

    # -- 2. 학습 로직 (Training Logic)

    def train_and_save_full_model(self) -> bool:
        """전체 데이터를 이용해 모델 학습 후 저장 (Full Training)"""
        logger.info("[ALS][TRAIN] Full Model Training Started.")

        # 1. 데이터 로드 및 행렬 생성
        matrix_bundle: MatrixBundle = self.data_loader.build_user_item_matrix()
        if matrix_bundle is None:
            logger.info("[ALS][TRAIN] No interaction data available. Skipping training.")
            return False

        # 데이터 로더에서 반환된 튜플 언팩
        matrix_coo, u_to_i, l_to_i, users, lectures = matrix_bundle
        # ALS 학습을 위해 CSR (Compressed Sparse Row) 포맷으로 변환
        matrix_csr: csr_matrix = matrix_coo.tocsr()

        # 2. ALS 모델 초기화
        model: AlternatingLeastSquares = AlternatingLeastSquares(
            factors=self.params.factors,
            regularization=self.params.regularization,
            iterations=self.params.iterations,
            calculate_training_loss=self.params.calculate_training_loss,
        )
        # 3. ALS 학습 실행 (implicit 라이브러리는 아이템-유저 행렬 (전치 행렬)을 사용)
        model.fit(matrix_csr.T)

        # 4. 모델 번들 객체 구성
        obj: Dict[str, Any] = {
            "model": model,
            "user_to_idx": u_to_i,
            "lecture_to_idx": l_to_i,
            "users": users,
            "lectures": lectures,
            "matrix": matrix_csr,
            "last_trained_at": timezone.now(),
        }

        # 5. 안전 저장 로직 호출
        return self._safe_dump_model(obj)

    def partial_fit_model_and_save(self) -> bool:
        """
        새로운 상호작용 데이터를 이용해 모델을 점진적 학습 후 저장.
        (기존 사용자 및 아이템 구성 유지)
        """
        logger.info("[ALS][PARTIAL] Partial Model Training Started.")

        # 1. 기존 모델 및 메타데이터 로드
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

        # 2. 기존 모델/매핑 불완전 시 전체 학습으로 폴백
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

        # 3. 새로운 상호작용 데이터 로드 (기존 사용자, 최종 학습 시점 이후 데이터만)
        partial_matrix_bundle: MatrixBundle = self.data_loader.build_user_item_matrix(
            users=old_users, last_trained_at=last_trained_at
        )

        if partial_matrix_bundle is None:
            logger.info("[ALS][PARTIAL] No new interaction data since last training. Skipping partial training.")
            return True

        # 부분 행렬은 인덱스 정보가 필요 없으므로 무시
        partial_matrix_coo: coo_matrix = partial_matrix_bundle[0]
        partial_matrix_csr: csr_matrix = partial_matrix_coo.tocsr()

        # 4. 행렬 차원 체크 (점진 학습은 사용자/아이템 수 변화를 허용하지 않음)
        if (
            partial_matrix_csr.shape[0] != old_matrix_csr.shape[0]
            or partial_matrix_csr.shape[1] != old_matrix_csr.shape[1]
        ):
            logger.warning(
                "[ALS][PARTIAL] Matrix shape mismatch (New user/item detected). Falling back to full training."
            )
            return self.train_and_save_full_model()

        # 5. 기존 행렬과 새로운 행렬을 합산하여 업데이트된 상호작용 행렬 생성
        # 행렬 합산 시 중복 상호작용 점수 누적
        updated_matrix_csr: csr_matrix = old_matrix_csr + partial_matrix_csr

        if settings.DEBUG:
            logger.debug(
                f"[ALS][PARTIAL] Matrix size updated from {old_matrix_csr.nnz} to {updated_matrix_csr.nnz} non-zero entries."
            )

        # 6. 점진적 학습 실행
        # 사용자 잠재 요인 업데이트: 기존 사용자 인덱스 전체 (0 ~ N-1)
        model.partial_fit_users(np.arange(updated_matrix_csr.shape[0]), updated_matrix_csr)
        # 아이템 잠재 요인 업데이트: 아이템-유저 행렬 (전치 행렬) 사용
        model.partial_fit_items(np.arange(updated_matrix_csr.shape[1]), updated_matrix_csr.T)

        # 7. 모델 번들 객체 업데이트 및 저장
        obj: Dict[str, Any] = {
            "model": model,
            "user_to_idx": u_to_i,
            "lecture_to_idx": l_to_i,
            "users": old_users,
            "lectures": old_lectures,
            "matrix": updated_matrix_csr,
            "last_trained_at": timezone.now(),
        }

        return self._safe_dump_model(obj)
