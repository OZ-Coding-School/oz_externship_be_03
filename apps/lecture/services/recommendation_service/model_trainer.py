import logging
import os
import shutil
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, cast

import implicit  # type: ignore
import joblib  # type: ignore
import numpy as np
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from implicit.als import AlternatingLeastSquares  # type: ignore
from scipy.sparse import csr_matrix

from apps.lecture.services.recommendation_service.constants import (
    ALS_MODEL_CACHE_KEY,
    ALS_PARAMS,
    ALS_TRAINING_LOCK_KEY,
    INITIAL_BACKOFF_SECONDS,
    L_IDX_TO_ID_CACHE_KEY,
    L_TO_IDX_CACHE_KEY,
    MAX_CACHE_LOAD_RETRIES,
    MODEL_VERSION,
    U_TO_IDX_CACHE_KEY,
    USER_ITEMS_MATRIX_CACHE_KEY,
    ALS_Hyperparameters,
)
from apps.lecture.services.recommendation_service.data_loader import (
    DataLoader,
    MatrixBundleExtended,
)

logger: logging.Logger = logging.getLogger(__name__)

MODEL_DIR: str = settings.MODEL_STORAGE_PATH
MODEL_BUNDLE_PATH: str = os.path.join(MODEL_DIR, f"als_model_bundle_{ALS_PARAMS.factors}f_{MODEL_VERSION}.joblib")
MODEL_BACKUP_PATH: str = MODEL_BUNDLE_PATH.replace(".joblib", "_backup.joblib")

ALS_CACHE_KEYS: List[str] = [
    ALS_MODEL_CACHE_KEY,
    U_TO_IDX_CACHE_KEY,
    L_TO_IDX_CACHE_KEY,
    L_IDX_TO_ID_CACHE_KEY,
    USER_ITEMS_MATRIX_CACHE_KEY,
]  # 캐시 무효화 대상 키 목록

ModelBundleReturn = Tuple[
    Optional[AlternatingLeastSquares],
    Optional[Dict[int, int]],
    Optional[Dict[int, int]],
    Optional[List[int]],
    Optional[List[int]],
    Optional[csr_matrix],
    Optional[datetime],
]  # load_model_and_mappings 반환 타입


class ModelTrainer:
    """
    ALS 모델 학습/저장/로드 및 캐시 동기화, atomic 저장, lock 기반 동시성 보호

    주요 기능:
    1. Full Training: 전체 데이터로 모델 학습
    2. Partial Training: 증분 학습 (신규 데이터만)
    3. Atomic 저장: 임시 파일 + 백업 + 롤백
    4. 동시성 제어: Redis 락 + exponential backoff
    5. 캐시 동기화: 모델 업데이트 시 캐시 무효화

    저장 형식:
    - joblib 직렬화 (protocol=4, xz 압축)
    - 모델 번들: {model, user_to_idx, lecture_to_idx, users, lectures, matrix, last_trained_at}

    Note:
        - MODEL_VERSION 변경 시 캐시 자동 무효화
        - implicit 라이브러리 버전 호환성 확인 필요
        - partial_fit은 shape 변경 불가 (신규 사용자/강의 시 Full Training 필수)
    """

    def __init__(self, data_loader: DataLoader) -> None:
        self.data_loader: DataLoader = data_loader
        self.params: ALS_Hyperparameters = ALS_PARAMS  # factors, regularization, iterations 등
        os.makedirs(MODEL_DIR, exist_ok=True)  # 디렉토리 없으면 생성
        logger.info(f"[ALS][INIT] Using implicit library version {implicit.__version__}")

    def _clear_redis_cache(self) -> None:
        """
        캐시 key 일괄 삭제 (모델 버전 무효화, 동기화)

        목적: 모델 업데이트 후 캐시 무효화

        처리:
        - ALS_CACHE_KEYS의 모든 키 삭제
        - 실패 시 에러 로그만 출력 (프로세스 계속)

        호출 시점:
        - 모델 저장 성공 후
        - 백업에서 복구 성공 후
        """
        try:
            cache.delete_many(ALS_CACHE_KEYS)  # 일괄 삭제
            logger.info(f"[ALS][CACHE] Model updated to {MODEL_VERSION}. Redis cache cleared.")
        except Exception as e:
            logger.error(f"[ALS][CACHE] Failed to clear Redis cache: {e}")

    def _safe_dump_model(self, obj: Dict[str, Any]) -> bool:
        """
        joblib atomic 저장, 임시파일 + protocol=4 + "xz" 압축,
        백업, rollback, metadata 로깅, 복구 후 캐시 무효화 재시도

        목적: 안전한 모델 저장 (원자성 보장)

        Args:
            obj: 모델 번들 딕셔너리
                - model: AlternatingLeastSquares 객체
                - user_to_idx: {user_id: matrix_index}
                - lecture_to_idx: {lecture_id: matrix_index}
                - users: [user_id, ...]
                - lectures: [lecture_id, ...]
                - matrix: csr_matrix (사용자-강의 상호작용)
                - last_trained_at: datetime (학습 시각)

        Returns:
            저장 성공 여부 (True/False)

        처리 흐름:
        1. 기존 파일 백업 (MODEL_BACKUP_PATH)
        2. 임시 파일에 저장 (MODEL_BUNDLE_PATH.tmp)
           - joblib.dump (protocol=4, xz 압축 레벨 3)
        3. 원자적 교체 (os.replace)
           - POSIX 보장: 다른 프로세스가 읽는 중에도 안전
        4. 백업 파일 삭제
        5. 메타데이터 로깅
           - 파일 크기 (MB)
           - 행렬 shape
           - Non-zero entries (nnz)
           - Sparsity (희소성)
        6. 캐시 무효화

        실패 시 복구:
        - 백업 파일이 있으면 복구 시도
        - 복구 성공 시 캐시 무효화 재시도
        - 복구 실패 시 CRITICAL 로그

        기술적 세부사항:
        - protocol=4: Python 3.4+ 호환
        - xz 압축: 높은 압축률 (레벨 3)
        - os.replace: 원자적 파일 교체 (POSIX)
        """
        tmp_path: str = MODEL_BUNDLE_PATH + ".tmp"  # 임시 파일 경로
        recovery_successful: bool = False  # 복구 성공 플래그

        # 1. 기존 파일 백업
        if os.path.exists(MODEL_BUNDLE_PATH):
            try:
                shutil.copyfile(MODEL_BUNDLE_PATH, MODEL_BACKUP_PATH)
                logger.info("[ALS][BACKUP] Existing model file backed up.")
            except Exception as e:
                logger.error(f"[ALS][BACKUP] Failed to create model backup: {e}")

        try:
            # 2. 임시 파일에 저장
            joblib.dump(obj, tmp_path, compress=("xz", 3), protocol=4)
            # 3. 원자적 교체
            os.replace(tmp_path, MODEL_BUNDLE_PATH)
            logger.info("[ALS][SAVE] Model saved atomically.")
            # 4. 백업 파일 삭제
            if os.path.exists(MODEL_BACKUP_PATH):
                os.remove(MODEL_BACKUP_PATH)
                if settings.DEBUG:
                    logger.debug("[ALS][BACKUP] Backup file deleted.")

            # 5. 메타데이터 로깅
            m_size_mb: float = os.path.getsize(MODEL_BUNDLE_PATH) / 1e6  # MB 단위
            matrix = obj.get("matrix")

            if matrix is not None and hasattr(matrix, "nnz"):
                nnz: int = matrix.nnz  # Non-zero entries
                total_elements: int = matrix.shape[0] * matrix.shape[1]
                sparsity: float = 1.0 - (nnz / total_elements) if total_elements > 0 else 0.0

                logger.info(
                    f"[ALS][METRICS] File size: {m_size_mb:.2f} MB, "
                    f"Matrix shape: {matrix.shape}, "
                    f"Non-zero entries: {nnz:,}, "
                    f"Sparsity: {sparsity:.4f}"
                )
            else:
                logger.info(f"[ALS][METRICS] File size: {m_size_mb:.2f} MB")

            # 6. 캐시 무효화
            self._clear_redis_cache()
            return True

        except Exception as e:
            logger.error(f"[ALS][SAVE] Error saving model bundle: {e}", exc_info=True)

            # 복구 시도
            if os.path.exists(MODEL_BACKUP_PATH):
                try:
                    shutil.move(MODEL_BACKUP_PATH, MODEL_BUNDLE_PATH)  # 백업에서 복구
                    logger.warning("[ALS][RECOVERY] Model save failed. Recovered from backup.")
                    recovery_successful = True
                except Exception as recovery_e:
                    logger.critical(f"[ALS][RECOVERY] CRITICAL: Failed to recover model from backup: {recovery_e}")

            # 복구 성공 시 캐시 무효화
            if recovery_successful:
                self._clear_redis_cache()

            return False

    def load_model_and_mappings(self) -> ModelBundleReturn:
        """
        모델 번들 파일 로드, 불완전시 모두 None 반환

        Returns:
            (model, user_to_idx, lecture_to_idx, users, lectures, matrix, last_trained_at)
            또는 실패 시 (None, None, None, None, None, None, None)

        처리:
        1. 파일 존재 확인
        2. joblib.load로 역직렬화
        3. last_trained_at을 timezone-aware로 변환
        4. 튜플로 반환

        실패 조건:
        - 파일 없음
        - 파일 손상
        - 역직렬화 실패
        """
        if not os.path.exists(MODEL_BUNDLE_PATH):
            logger.info("[ALS][LOAD] Model bundle file not found.")
            return None, None, None, None, None, None, None
        try:
            data: Dict[str, Any] = joblib.load(MODEL_BUNDLE_PATH)

            # last_trained_at timezone-aware 변환
            last_trained_at = data.get("last_trained_at")
            if last_trained_at is not None and last_trained_at.tzinfo is None:
                last_trained_at = timezone.make_aware(last_trained_at)

            logger.info("[ALS][LOAD] Model bundle loaded successfully.")
            return cast(
                ModelBundleReturn,
                (
                    data.get("model"),
                    data.get("user_to_idx"),
                    data.get("lecture_to_idx"),
                    data.get("users"),
                    data.get("lectures"),
                    data.get("matrix"),
                    last_trained_at,
                ),
            )
        except Exception as e:
            logger.error(f"[ALS][LOAD] Error loading model bundle: {e}", exc_info=True)
            return None, None, None, None, None, None, None

    def _acquire_lock_with_retry(self, lock_key: str, timeout: int) -> bool:
        """
        Exponential backoff를 사용한 Redis 락 획득 재시도

        Args:
            lock_key: Redis 락 키
            timeout: 락 타임아웃 (초)

        Returns:
            락 획득 성공 여부 (True/False)

        처리 로직:
        1. 최대 MAX_CACHE_LOAD_RETRIES 횟수만큼 재시도 (5회)
        2. 각 재시도마다 exponential backoff 적용
           - 1초 → 2초 → 4초 → 8초 → 16초
        3. 락 획득 성공 시 즉시 True 반환
        4. 모든 재시도 실패 시 False 반환

        총 대기 시간: 최대 31초 (1+2+4+8+16)

        사용 이유:
        - 동시에 여러 프로세스가 모델 학습 시도 방지
        - 락 경합 시 무한 대기 대신 재시도 후 포기
        """
        redis_cache = cast(Any, cache)

        for attempt in range(MAX_CACHE_LOAD_RETRIES):
            try:
                # cache.add는 키가 없을 때만 성공 (락 획득)
                if redis_cache.add(lock_key, True, timeout=timeout):
                    logger.debug(f"[ALS][LOCK] Lock acquired on attempt {attempt + 1}")
                    return True
            except Exception as e:
                logger.warning(f"[ALS][LOCK] Lock acquisition attempt {attempt + 1} failed: {e}")

            # 마지막 시도가 아니면 백오프 대기
            if attempt < MAX_CACHE_LOAD_RETRIES - 1:
                backoff = INITIAL_BACKOFF_SECONDS * (2**attempt)  # 지수 증가
                logger.info(
                    f"[ALS][LOCK] Lock busy. Retry {attempt + 1}/{MAX_CACHE_LOAD_RETRIES} "
                    f"after {backoff:.1f}s backoff"
                )
                time.sleep(backoff)

        logger.error(f"[ALS][LOCK] Failed to acquire lock after {MAX_CACHE_LOAD_RETRIES} retries")
        return False

    def train_and_save_full_model(self) -> bool:
        """
        전체 행렬로 ALS 모델 학습 및 저장, exponential backoff 락

        Returns:
            학습 및 저장 성공 여부 (True/False)

        처리 흐름:
        1. DataLoader로 전체 사용자-강의 행렬 구축
        2. ALS 모델 초기화 (하이퍼파라미터 적용)
        3. 학습 시간 측정 시작
        4. 모델 학습 (item-user 전치(transpose) 행렬 사용)
        5. 학습 시간 로깅
        6. 모델 번들 생성
        7. Exponential backoff로 Redis 락 획득 후 저장

        Note:
            - 상호작용 데이터 없으면 학습 스킵
            - Implicit ALS 모델은 item-user 행렬을 기대하므로, data_loader의 사용자-아이템 행렬을 전치하여 전달해야 함.
            - 락 획득 실패 시 exponential backoff로 재시도
            - 학습 완료 후 반드시 락 해제
        """
        logger.info("[ALS][TRAIN] Full Model Training Started.")

        # 1. 데이터 로드
        matrix_bundle_ext: MatrixBundleExtended = self.data_loader.build_user_item_matrix(
            existing_users=None,  # 전체 사용자
            last_trained_at=None,  # 전체 기간
            return_format="csr",  # CSR 희소 행렬
        )

        if matrix_bundle_ext is None:
            logger.info("[ALS][TRAIN] No interaction data available. Skipping training.")
            return False

        matrix_csr, u_to_i, l_to_i, users, lectures, _ = matrix_bundle_ext

        # 2. 모델 초기화
        model: AlternatingLeastSquares = AlternatingLeastSquares(
            factors=self.params.factors,  # 잠재 요인 개수 (예: 50)
            regularization=self.params.regularization,  # 정규화 계수
            iterations=self.params.iterations,  # 반복 횟수 (예: 15)
            calculate_training_loss=self.params.calculate_training_loss,  # 손실 계산 여부
        )

        # 3. 학습 실행
        logger.info(f"[ALS][TRAIN] Training model with matrix shape: {matrix_csr.shape}")
        start_time = time.time()

        # ALS는 item-user 행렬을 기대하므로 전치
        # matrix_csr: (users x items) → matrix_csr.T: (items x users)
        model.fit(matrix_csr.T)

        training_time = time.time() - start_time
        logger.info(f"[ALS][TRAIN] Model training completed in {training_time:.2f} seconds.")

        # 4. 모델 번들 생성
        obj: Dict[str, Any] = {
            "model": model,
            "user_to_idx": u_to_i,
            "lecture_to_idx": l_to_i,
            "users": users,
            "lectures": lectures,
            "matrix": matrix_csr,
            "last_trained_at": timezone.now(),
        }

        # 5. 락 획득 및 저장
        if not self._acquire_lock_with_retry(ALS_TRAINING_LOCK_KEY, timeout=600):
            logger.error("[ALS][LOCK] Failed to acquire training lock after retries.")
            return False

        try:
            return self._safe_dump_model(obj)
        finally:
            # 락 해제 (성공/실패 무관)
            try:
                cache.delete(ALS_TRAINING_LOCK_KEY)
                logger.debug("[ALS][LOCK] Training lock released.")
            except Exception as e:
                logger.warning(f"[ALS][LOCK] Failed to release lock: {e}")

    def partial_fit_model_and_save(self) -> bool:
        """
        점진학습: 기존 모델/매핑 기반 신규 행렬 합산

        Returns:
            학습 및 저장 성공 여부 (True/False)

        처리 흐름:
        1. 기존 모델 번들 로드
        2. 신규 상호작용 데이터로 부분 행렬 구축
        3. 신규 사용자/강의 감지 시 Full Training으로 폴백
        4. Shape 검증 (사용자 수, 강의 수 일치 확인)
        5. 행렬 합산 및 partial_fit 적용
        6. Exponential backoff로 Redis 락 획득 후 저장

        폴백 조건 (Full Training으로 전환):
        - 기존 모델 없거나 불완전
        - 신규 사용자 감지
        - 신규 강의 감지
        - Shape 불일치 (사용자 수)
        - implicit partial_fit 실패

        주의사항:
        - implicit의 partial_fit은 shape 변경 불가
        - 신규 강의 유입 시 Full Training 필수
        - 기존 사용자의 신규 상호작용만 안전하게 처리 가능

        Note:
            - 신규 데이터 없으면 학습 스킵 (True 반환)
            - 락 획득 실패 시 exponential backoff로 재시도
        """
        logger.info("[ALS][PARTIAL] Partial Model Training Started.")

        # 1. 기존 모델 로드
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

        # 기존 모델 검증
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

            # Timezone-aware 변환드
            last_trained_at = timezone.make_aware(last_trained_at)

        # 2. 신규 데이터 로
        partial_matrix_bundle_ext: MatrixBundleExtended = self.data_loader.build_user_item_matrix(
            existing_users=old_users,  # 기존 사용자 목록
            last_trained_at=last_trained_at,  # 마지막 학습 시각 이후
            return_format="csr",
        )

        if partial_matrix_bundle_ext is None:
            logger.info("[ALS][PARTIAL] No new interaction data since last training. Skipping partial training.")
            return True  # 신규 데이터 없음 (성공으로 간주)

        partial_matrix_csr, new_u_to_i, new_l_to_i, updated_users, updated_lectures, is_new_user_added = (
            partial_matrix_bundle_ext
        )

        # 3. 신규 사용자 유입 확인
        if is_new_user_added:
            logger.warning(
                f"[ALS][PARTIAL] New user(s) detected since {last_trained_at}. Falling back to full training."
            )
            return self.train_and_save_full_model()

        # 4. Shape 검증: 사용자 수
        if partial_matrix_csr.shape[0] != old_matrix_csr.shape[0]:
            logger.error("[ALS][PARTIAL] User shape mismatch despite no new user flag. Falling back to full training.")
            return self.train_and_save_full_model()

        # 5. Shape 검증: 강의 수
        if partial_matrix_csr.shape[1] != old_matrix_csr.shape[1]:
            # 신규 강의 ID 확인
            if old_lectures is None:
                logger.error("[ALS][PARTIAL] old_lectures is None. Falling back to full training.")
                return self.train_and_save_full_model()

            old_lecture_set = set(old_lectures)
            new_lecture_set = set(updated_lectures)
            new_lectures_added = new_lecture_set - old_lecture_set

            if new_lectures_added:
                logger.warning(
                    f"[ALS][PARTIAL] New lecture(s) detected: {len(new_lectures_added)} items. "
                    "Falling back to full training."
                )
                return self.train_and_save_full_model()

            # 6. 행렬 확장 (신규 강의 없지만 shape 다른 경우)
            # 부분 행렬이 기존보다 작은 경우: 일부 강의만 상호작용 발생
            logger.info(
                f"[ALS][PARTIAL] Partial matrix has fewer lectures ({partial_matrix_csr.shape[1]}) "
                f"than old matrix ({old_matrix_csr.shape[1]}). Expanding to match."
            )

            # 인덱스 매핑 계산 (NumPy 벡터화)
            # 목적: 부분 행렬의 강의 인덱스를 기존 행렬의 인덱스로 변환
            col_mapping = np.full(partial_matrix_csr.shape[1], -1, dtype=np.int32)  # 초기값 -1 (매핑 없음)
            # 각 신규 강의 ID를 기존 인덱스로 매핑
            for new_lec_id, new_idx in new_l_to_i.items():
                if new_lec_id in l_to_i:  # 기존 매핑에 존재하는 강의만
                    col_mapping[new_idx] = l_to_i[new_lec_id]  # 신규 인덱스 → 기존 인덱스

            # 유효한 매핑만 필터링
            valid_mask = col_mapping >= 0  # -1이 아닌 것만 (매핑 성공)
            valid_new_cols = np.where(valid_mask)[0]  # 부분 행렬의 유효 열 인덱스
            valid_old_cols = col_mapping[valid_mask]  # 기존 행렬의 대응 열 인덱스

            # partial_matrix_csr를 명시적으로 CSR로 변환: 타입 체커 만족 + 슬라이싱 최적화
            partial_matrix_csr_typed: csr_matrix = partial_matrix_csr.tocsr()

            # 빈 행렬 생성 (기존 행렬과 동일한 shape) - csr_matrix 생성 시 타입 추론 한계 우회
            expanded_partial_csr: csr_matrix = csr_matrix(  # type: ignore[type-var]
                (old_matrix_csr.shape[0], old_matrix_csr.shape[1]), dtype=np.float32
            ).tocsr()

            # 벡터화된 슬라이싱으로 데이터 복사
            # 부분 행렬의 유효 열을 기존 행렬의 대응 위치에 배치
            # 슬라이싱 할당 시 타입 불일치 우회
            expanded_partial_csr[:, valid_old_cols] = partial_matrix_csr_typed[
                :, valid_new_cols
            ]  # type: ignore[assignment]

            # 확장된 행렬로 교체
            partial_matrix_csr = expanded_partial_csr

        # 7. 최종 행렬 합산
        # 기존 행렬 + 신규 상호작용 행렬
        updated_matrix_csr: csr_matrix = old_matrix_csr + partial_matrix_csr

        if settings.DEBUG:
            logger.debug(
                f"[ALS][PARTIAL] Matrix size updated from {old_matrix_csr.nnz} "
                f"to {updated_matrix_csr.nnz} non-zero entries."
            )

        # 8. implicit 버전 호환성에 따라 partial_fit 함수 적용
        try:
            logger.info("[ALS][PARTIAL] Applying partial_fit to model.")
            start_time = time.time()

            # 사용자 업데이트
            # np.arange(N): 0부터 N-1까지의 인덱스 배열
            model.partial_fit_users(np.arange(updated_matrix_csr.shape[0]), updated_matrix_csr)
            # 강의 업데이트 (전치 행렬 사용)
            model.partial_fit_items(np.arange(updated_matrix_csr.shape[1]), updated_matrix_csr.T)

            partial_fit_time = time.time() - start_time
            logger.info(f"[ALS][PARTIAL] Partial fit completed successfully in {partial_fit_time:.2f} seconds.")
        except Exception as e:
            # Partial fit 실패 시 Full Training으로 폴백
            logger.error(f"[ALS][LIB] Implicit partial_fit error: {e}. Falling back to full training.", exc_info=True)
            return self.train_and_save_full_model()

        # 9. 모델 번들 생성
        obj: Dict[str, Any] = {
            "model": model,  # 업데이트된 모델
            "user_to_idx": u_to_i,  # 기존 사용자 매핑 유지
            "lecture_to_idx": l_to_i,  # 기존 강의 매핑 유지
            "users": old_users,  # 기존 사용자 목록 유지
            "lectures": old_lectures,  # 기존 강의 목록 유지
            "matrix": updated_matrix_csr,  # 합산된 행렬
            "last_trained_at": timezone.now(),  # 현재 시각으로 업데이트
        }

        # 10. 락 획득 및 저장
        # Exponential backoff로 락 획득
        if not self._acquire_lock_with_retry(ALS_TRAINING_LOCK_KEY, timeout=600):
            logger.error("[ALS][LOCK] Failed to acquire training lock for partial fit after retries.")
            return False

        try:
            result = self._safe_dump_model(obj)
            # 11. 캐시 무효화
            # 저장 성공 시 모든 캐시 삭제
            if result:
                cache.delete(ALS_MODEL_CACHE_KEY)
                cache.delete(U_TO_IDX_CACHE_KEY)
                cache.delete(L_TO_IDX_CACHE_KEY)
                cache.delete(L_IDX_TO_ID_CACHE_KEY)
                cache.delete(USER_ITEMS_MATRIX_CACHE_KEY)
                logger.info("[ALS][CACHE] All caches invalidated after partial fit")

            return result
        finally:
            # 12. 락 해제 (성공/실패 무관)
            try:
                cache.delete(ALS_TRAINING_LOCK_KEY)
                logger.debug("[ALS][LOCK] Partial fit lock released.")
            except Exception as e:
                logger.warning(f"[ALS][LOCK] Failed to release lock: {e}")
