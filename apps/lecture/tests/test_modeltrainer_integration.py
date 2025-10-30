from __future__ import annotations

import os
import shutil
import tempfile
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import Mock, patch

import numpy as np
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from implicit.als import AlternatingLeastSquares  # type: ignore
from scipy.sparse import csr_matrix

from apps.core.utils.isolated_cache_testcase import IsolatedRedisTestClient
from apps.lecture.services.recommendation_service.constants import (
    ALS_MODEL_CACHE_KEY,
    ALS_PARAMS,
    ALS_TRAINING_LOCK_KEY,
    L_IDX_TO_ID_CACHE_KEY,
    L_TO_IDX_CACHE_KEY,
    U_TO_IDX_CACHE_KEY,
    USER_ITEMS_MATRIX_CACHE_KEY,
)
from apps.lecture.services.recommendation_service.data_loader import DataLoader
from apps.lecture.services.recommendation_service.model_trainer import ModelTrainer


class ModelTrainerIntegrationTest(IsolatedRedisTestClient):
    """ModelTrainer 통합 테스트 - 실제 파일 시스템과 격리된 Redis 캐시 사용"""

    def setUp(self) -> None:
        """각 테스트 전 임시 디렉토리 및 캐시 초기화"""
        super().setUp()
        cache.clear()

        # 임시 모델 저장 디렉토리 생성
        self.temp_dir: str = tempfile.mkdtemp()

        # 테스트용 모델 버전
        self.test_model_version: str = f"test_{timezone.now().strftime('%Y%m%d_%H%M%S')}"

        # Settings 및 모델 버전 오버라이드
        self.settings_override = override_settings(
            MODEL_STORAGE_PATH=self.temp_dir,
        )
        self.settings_override.enable()

        # MODEL_VERSION과 MODEL_BUNDLE_PATH를 모두 패치
        self.model_version_patcher = patch(
            "apps.lecture.services.recommendation_service.model_trainer.MODEL_VERSION",
            self.test_model_version,
        )
        self.model_version_patcher.start()

        # MODEL_BUNDLE_PATH도 패치 (모델 버전이 포함된 경로)
        self.model_bundle_path = os.path.join(
            self.temp_dir,
            f"als_model_bundle_{ALS_PARAMS.factors}f_{self.test_model_version}.joblib",
        )
        self.model_bundle_path_patcher = patch(
            "apps.lecture.services.recommendation_service.model_trainer.MODEL_BUNDLE_PATH",
            self.model_bundle_path,
        )
        self.model_bundle_path_patcher.start()

        # Mock DataLoader 생성
        self.mock_data_loader: Mock = Mock(spec=DataLoader)

        # ModelTrainer 인스턴스 생성
        self.trainer: ModelTrainer = ModelTrainer(self.mock_data_loader)

    def tearDown(self) -> None:
        """테스트 후 임시 파일 정리"""
        # 패처 중지
        self.model_version_patcher.stop()
        self.model_bundle_path_patcher.stop()

        self.settings_override.disable()

        # 임시 디렉토리 삭제
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

        super().tearDown()

    def _create_mock_matrix_bundle(
        self, num_users: int = 10, num_lectures: int = 20
    ) -> Tuple[csr_matrix, Dict[int, int], Dict[int, int], List[int], List[int], bool]:
        """테스트용 mock 행렬 번들 생성"""
        # 희소 행렬 생성 (사용자-강의 상호작용)
        np.random.seed(42)  # 재현성을 위한 시드 설정
        data: np.ndarray = np.random.rand(num_users * 2).astype(np.float32)
        row: np.ndarray = np.random.randint(0, num_users, num_users * 2)
        col: np.ndarray = np.random.randint(0, num_lectures, num_users * 2)
        matrix: csr_matrix = csr_matrix((data, (row, col)), shape=(num_users, num_lectures), dtype=np.float32)

        # 매핑 생성
        user_to_idx: Dict[int, int] = {i: i for i in range(num_users)}
        lecture_to_idx: Dict[int, int] = {i: i for i in range(num_lectures)}
        users: List[int] = list(range(num_users))
        lectures: List[int] = list(range(num_lectures))

        return matrix, user_to_idx, lecture_to_idx, users, lectures, False

    def test_train_and_save_full_model_success(self) -> None:
        """Full Training: 모델 학습 및 저장 성공 테스트"""
        # Mock 데이터 설정
        matrix_bundle: Tuple[csr_matrix, Dict[int, int], Dict[int, int], List[int], List[int], bool] = (
            self._create_mock_matrix_bundle()
        )
        self.mock_data_loader.build_user_item_matrix.return_value = matrix_bundle

        # 학습 실행
        result: bool = self.trainer.train_and_save_full_model()

        # 검증
        self.assertTrue(result)
        self.mock_data_loader.build_user_item_matrix.assert_called_once_with(
            existing_users=None, last_trained_at=None, return_format="csr"
        )

        # 모델 파일 생성 확인
        model_files: List[str] = [f for f in os.listdir(self.temp_dir) if f.endswith(".joblib") and "backup" not in f]
        self.assertGreater(len(model_files), 0)

    def test_train_and_save_full_model_no_data(self) -> None:
        """Full Training: 상호작용 데이터 없을 때 학습 스킵"""
        # 빈 데이터 반환
        self.mock_data_loader.build_user_item_matrix.return_value = None

        # 학습 실행
        result: bool = self.trainer.train_and_save_full_model()

        # 검증
        self.assertFalse(result)

        # 모델 파일 생성되지 않음
        model_files: List[str] = [f for f in os.listdir(self.temp_dir) if f.endswith(".joblib")]
        self.assertEqual(len(model_files), 0)

    def test_load_model_and_mappings_success(self) -> None:
        """모델 로드: 저장된 모델 정상 로드 테스트"""
        # 먼저 모델 저장
        matrix_bundle: Tuple[csr_matrix, Dict[int, int], Dict[int, int], List[int], List[int], bool] = (
            self._create_mock_matrix_bundle()
        )
        self.mock_data_loader.build_user_item_matrix.return_value = matrix_bundle
        save_result: bool = self.trainer.train_and_save_full_model()
        self.assertTrue(save_result)

        # 캐시 초기화 (파일에서 로드하도록)
        cache.clear()

        # 모델 로드
        loaded_bundle: Tuple[
            Optional[AlternatingLeastSquares],
            Optional[Dict[int, int]],
            Optional[Dict[int, int]],
            Optional[List[int]],
            Optional[List[int]],
            Optional[csr_matrix],
            Optional[datetime],
        ] = self.trainer.load_model_and_mappings()

        # 검증
        model, u_to_idx, l_to_idx, users, lectures, matrix, last_trained_at = loaded_bundle

        self.assertIsNotNone(model)
        self.assertIsNotNone(u_to_idx)
        self.assertIsNotNone(l_to_idx)
        self.assertIsNotNone(users)
        self.assertIsNotNone(lectures)
        self.assertIsNotNone(matrix)
        self.assertIsNotNone(last_trained_at)

        # Type narrowing을 위한 assert 추가
        assert u_to_idx is not None
        assert l_to_idx is not None

        self.assertEqual(len(u_to_idx), 10)
        self.assertEqual(len(l_to_idx), 20)

    def test_load_model_and_mappings_no_model(self) -> None:
        """모델 로드: 저장된 모델 없을 때 None 반환"""
        # 캐시와 파일 시스템 모두 비어있는지 확인
        cache.clear()

        # 모델 로드 시도
        loaded_bundle: Tuple[
            Optional[AlternatingLeastSquares],
            Optional[Dict[int, int]],
            Optional[Dict[int, int]],
            Optional[List[int]],
            Optional[List[int]],
            Optional[csr_matrix],
            Optional[datetime],
        ] = self.trainer.load_model_and_mappings()

        model, u_to_idx, l_to_idx, users, lectures, matrix, last_trained_at = loaded_bundle

        # 모델이 없으므로 모두 None이어야 함
        self.assertIsNone(model)
        self.assertIsNone(u_to_idx)
        self.assertIsNone(l_to_idx)
        self.assertIsNone(users)
        self.assertIsNone(lectures)
        self.assertIsNone(matrix)
        self.assertIsNone(last_trained_at)

    def test_safe_dump_model_atomic_save(self) -> None:
        """모델 저장: Atomic 저장 메커니즘 테스트"""
        # 모델 번들 생성
        matrix_bundle: Tuple[csr_matrix, Dict[int, int], Dict[int, int], List[int], List[int], bool] = (
            self._create_mock_matrix_bundle()
        )
        matrix, u_to_idx, l_to_idx, users, lectures, _ = matrix_bundle

        model: AlternatingLeastSquares = AlternatingLeastSquares(
            factors=ALS_PARAMS.factors,
            regularization=ALS_PARAMS.regularization,
            iterations=5,
        )
        model.fit(matrix.T)

        obj: Dict[str, Any] = {
            "model": model,
            "user_to_idx": u_to_idx,
            "lecture_to_idx": l_to_idx,
            "users": users,
            "lectures": lectures,
            "matrix": matrix,
            "last_trained_at": timezone.now(),
        }

        # 저장 실행
        result: bool = self.trainer._safe_dump_model(obj)

        # 검증
        self.assertTrue(result)

        # 임시 파일이 삭제되었는지 확인
        temp_files: List[str] = [f for f in os.listdir(self.temp_dir) if f.endswith(".tmp")]
        self.assertEqual(len(temp_files), 0)

        # 백업 파일이 삭제되었는지 확인
        backup_files: List[str] = [f for f in os.listdir(self.temp_dir) if "backup" in f]
        self.assertEqual(len(backup_files), 0)

    def test_safe_dump_model_with_backup_recovery(self) -> None:
        """모델 저장: 백업 복구 메커니즘 테스트"""
        # 먼저 정상 모델 저장
        matrix_bundle: Tuple[csr_matrix, Dict[int, int], Dict[int, int], List[int], List[int], bool] = (
            self._create_mock_matrix_bundle()
        )
        self.mock_data_loader.build_user_item_matrix.return_value = matrix_bundle
        self.trainer.train_and_save_full_model()

        # 기존 모델 파일 경로 확인
        model_files: List[str] = [f for f in os.listdir(self.temp_dir) if f.endswith(".joblib") and "backup" not in f]
        self.assertEqual(len(model_files), 1)
        original_model_path: str = os.path.join(self.temp_dir, model_files[0])

        # 손상된 데이터로 저장 시도 (joblib.dump 실패 시뮬레이션)
        with patch("joblib.dump", side_effect=Exception("Simulated save error")):
            matrix_bundle2: Tuple[csr_matrix, Dict[int, int], Dict[int, int], List[int], List[int], bool] = (
                self._create_mock_matrix_bundle(num_users=15)
            )
            matrix2, u_to_idx2, l_to_idx2, users2, lectures2, _ = matrix_bundle2

            model2: AlternatingLeastSquares = AlternatingLeastSquares(
                factors=ALS_PARAMS.factors,
                regularization=ALS_PARAMS.regularization,
                iterations=5,
            )
            model2.fit(matrix2.T)

            obj2: Dict[str, Any] = {
                "model": model2,
                "user_to_idx": u_to_idx2,
                "lecture_to_idx": l_to_idx2,
                "users": users2,
                "lectures": lectures2,
                "matrix": matrix2,
                "last_trained_at": timezone.now(),
            }

            result: bool = self.trainer._safe_dump_model(obj2)

            # 저장 실패 확인
            self.assertFalse(result)

            # 원본 모델 파일이 복구되었는지 확인
        self.assertTrue(os.path.exists(original_model_path))

    def test_clear_redis_cache(self) -> None:
        """캐시 무효화: Redis 캐시 삭제 테스트"""
        # 캐시에 데이터 설정
        cache.set(ALS_MODEL_CACHE_KEY, "test_model")
        cache.set(U_TO_IDX_CACHE_KEY, {"1": 0})
        cache.set(L_TO_IDX_CACHE_KEY, {"1": 0})
        cache.set(L_IDX_TO_ID_CACHE_KEY, {"0": 1})
        cache.set(USER_ITEMS_MATRIX_CACHE_KEY, "test_matrix")

        # 캐시 삭제 실행
        self.trainer._clear_redis_cache()

        # 검증
        self.assertIsNone(cache.get(ALS_MODEL_CACHE_KEY))
        self.assertIsNone(cache.get(U_TO_IDX_CACHE_KEY))
        self.assertIsNone(cache.get(L_TO_IDX_CACHE_KEY))
        self.assertIsNone(cache.get(L_IDX_TO_ID_CACHE_KEY))
        self.assertIsNone(cache.get(USER_ITEMS_MATRIX_CACHE_KEY))

    def test_acquire_lock_with_retry_success(self) -> None:
        """락 획득: 첫 시도에 성공하는 경우"""
        lock_key: str = "test_lock_key"
        timeout: int = 60

        # Backoff 시간을 줄여서 테스트 (0.1초로 설정)
        with patch("apps.lecture.services.recommendation_service.model_trainer.INITIAL_BACKOFF_SECONDS", 0.1):
            result: bool = self.trainer._acquire_lock_with_retry(lock_key, timeout)

            # 검증
        self.assertTrue(result)

        # 락이 설정되었는지 확인
        self.assertIsNotNone(cache.get(lock_key))

        # 정리
        cache.delete(lock_key)

    def test_acquire_lock_with_retry_exponential_backoff(self) -> None:
        """락 획득: Exponential backoff 재시도 테스트"""
        lock_key: str = ALS_TRAINING_LOCK_KEY
        timeout: int = 60

        # 먼저 락 설정 (다른 프로세스가 락을 보유한 상황 시뮬레이션)
        cache.set(lock_key, True, timeout=timeout)

        # Backoff 시간을 줄여서 테스트 (0.01초로 설정)
        with patch("apps.lecture.services.recommendation_service.model_trainer.INITIAL_BACKOFF_SECONDS", 0.01):
            with patch("time.sleep") as mock_sleep:  # sleep을 mock하여 테스트 속도 향상
                result: bool = self.trainer._acquire_lock_with_retry(lock_key, timeout)

                # 검증
                self.assertFalse(result)

                # Exponential backoff가 호출되었는지 확인
                self.assertGreater(mock_sleep.call_count, 0)

                # 정리
        cache.delete(lock_key)

    def test_partial_fit_model_fallback_to_full_training_no_base_model(self) -> None:
        """Partial Fit: 기존 모델 없을 때 Full Training으로 폴백"""
        # 기존 모델 없음 (파일 시스템에 모델 파일 없음)

        # Mock 데이터 설정 (Full Training용)
        matrix_bundle: Tuple[csr_matrix, Dict[int, int], Dict[int, int], List[int], List[int], bool] = (
            self._create_mock_matrix_bundle()
        )
        self.mock_data_loader.build_user_item_matrix.return_value = matrix_bundle

        # Partial Fit 시도 (기존 모델 없으므로 Full Training으로 폴백)
        existing_users: List[int] = [0, 1, 2]
        last_trained_at: datetime = timezone.now() - timedelta(days=1)

        result: bool = self.trainer.partial_fit_model_and_save()

        # Full Training이 호출되었는지 확인
        self.assertTrue(result)

        # 모델 파일이 생성되었는지 확인
        model_files: List[str] = [f for f in os.listdir(self.temp_dir) if f.endswith(".joblib") and "backup" not in f]
        self.assertGreater(len(model_files), 0)

    def test_partial_fit_model_with_new_users(self) -> None:
        """Partial Fit: 신규 사용자 감지 시 Full Training으로 폴백"""
        # 먼저 기존 모델 생성
        matrix_bundle: Tuple[csr_matrix, Dict[int, int], Dict[int, int], List[int], List[int], bool] = (
            self._create_mock_matrix_bundle(num_users=10)
        )
        self.mock_data_loader.build_user_item_matrix.return_value = matrix_bundle
        self.trainer.train_and_save_full_model()

        # 신규 사용자가 포함된 Partial Fit 데이터 (is_new_user_added=True)
        partial_matrix_bundle: Tuple[csr_matrix, Dict[int, int], Dict[int, int], List[int], List[int], bool] = (
            self._create_mock_matrix_bundle(num_users=12)
        )
        matrix, u_to_idx, l_to_idx, users, lectures, is_new_user = partial_matrix_bundle

        # is_new_user_added=True로 설정
        partial_matrix_bundle_with_new_user: Tuple[
            csr_matrix, Dict[int, int], Dict[int, int], List[int], List[int], bool
        ] = (matrix, u_to_idx, l_to_idx, users, lectures, True)

        self.mock_data_loader.build_user_item_matrix.return_value = partial_matrix_bundle_with_new_user

        existing_users: List[int] = list(range(10))
        last_trained_at: datetime = timezone.now() - timedelta(days=1)

        result: bool = self.trainer.partial_fit_model_and_save()

        # Full Training으로 폴백되어야 함
        self.assertTrue(result)

    def test_load_model_and_mappings_from_cache(self) -> None:
        """모델 로드: Redis 캐시에서 로드 성공"""
        # 먼저 모델 학습 및 저장
        matrix_bundle: Tuple[csr_matrix, Dict[int, int], Dict[int, int], List[int], List[int], bool] = (
            self._create_mock_matrix_bundle()
        )
        self.mock_data_loader.build_user_item_matrix.return_value = matrix_bundle
        self.trainer.train_and_save_full_model()

        # 캐시에 모델 데이터 설정 (실제로는 train_and_save_full_model에서 설정됨)
        matrix, u_to_idx, l_to_idx, users, lectures, _ = matrix_bundle

        model: AlternatingLeastSquares = AlternatingLeastSquares(
            factors=ALS_PARAMS.factors,
            regularization=ALS_PARAMS.regularization,
            iterations=5,
        )
        model.fit(matrix.T)

        cache.set(ALS_MODEL_CACHE_KEY, model)
        cache.set(U_TO_IDX_CACHE_KEY, u_to_idx)
        cache.set(L_TO_IDX_CACHE_KEY, l_to_idx)
        cache.set(L_IDX_TO_ID_CACHE_KEY, {i: lid for lid, i in l_to_idx.items()})
        cache.set(USER_ITEMS_MATRIX_CACHE_KEY, matrix)

        # 모델 로드
        loaded_bundle: Tuple[
            Optional[AlternatingLeastSquares],
            Optional[Dict[int, int]],
            Optional[Dict[int, int]],
            Optional[List[int]],
            Optional[List[int]],
            Optional[csr_matrix],
            Optional[datetime],
        ] = self.trainer.load_model_and_mappings()

        # 검증
        loaded_model, loaded_u_to_idx, loaded_l_to_idx, loaded_users, loaded_lectures, loaded_matrix, last_trained = (
            loaded_bundle
        )

        self.assertIsNotNone(loaded_model)
        self.assertIsNotNone(loaded_u_to_idx)
        self.assertIsNotNone(loaded_l_to_idx)
        self.assertEqual(loaded_u_to_idx, u_to_idx)
        self.assertEqual(loaded_l_to_idx, l_to_idx)

    def test_model_version_isolation(self) -> None:
        """모델 버전: 버전별 격리 테스트"""
        # 첫 번째 버전으로 모델 학습
        matrix_bundle1: Tuple[csr_matrix, Dict[int, int], Dict[int, int], List[int], List[int], bool] = (
            self._create_mock_matrix_bundle(num_users=10)
        )
        self.mock_data_loader.build_user_item_matrix.return_value = matrix_bundle1
        self.trainer.train_and_save_full_model()

        # 첫 번째 버전의 모델 파일 확인
        model_files_v1: List[str] = [
            f for f in os.listdir(self.temp_dir) if self.test_model_version in f and f.endswith(".joblib")
        ]
        self.assertGreater(len(model_files_v1), 0)

        # 다른 버전으로 새 trainer 생성
        new_version: str = f"test_{timezone.now().strftime('%Y%m%d_%H%M%S')}_v2"

        # 새 버전의 MODEL_BUNDLE_PATH 생성
        new_model_bundle_path: str = os.path.join(
            self.temp_dir, f"als_model_bundle_{ALS_PARAMS.factors}f_{new_version}.joblib"
        )

        # 새 버전으로 패치
        with patch("apps.lecture.services.recommendation_service.model_trainer.MODEL_VERSION", new_version):
            with patch(
                "apps.lecture.services.recommendation_service.model_trainer.MODEL_BUNDLE_PATH", new_model_bundle_path
            ):
                trainer2: ModelTrainer = ModelTrainer(self.mock_data_loader)

                # 새 버전으로 모델 학습
                matrix_bundle2: Tuple[csr_matrix, Dict[int, int], Dict[int, int], List[int], List[int], bool] = (
                    self._create_mock_matrix_bundle(num_users=15)
                )
                self.mock_data_loader.build_user_item_matrix.return_value = matrix_bundle2
                trainer2.train_and_save_full_model()

                # 두 버전의 모델 파일이 모두 존재하는지 확인
        all_model_files: List[str] = [
            f for f in os.listdir(self.temp_dir) if f.endswith(".joblib") and "backup" not in f
        ]
        self.assertGreaterEqual(len(all_model_files), 2)

        # 각 버전의 파일이 존재하는지 확인
        v1_exists: bool = any(self.test_model_version in f for f in all_model_files)
        v2_exists: bool = any(new_version in f for f in all_model_files)

        self.assertTrue(v1_exists, f"Version 1 model file not found: {self.test_model_version}")
        self.assertTrue(v2_exists, f"Version 2 model file not found: {new_version}")

    def test_partial_fit_user_shape_mismatch(self) -> None:
        """Partial Fit: 사용자 수 불일치 시 Full Training 폴백"""
        # 기존 모델 생성 (10명 사용자)
        matrix_bundle: Tuple[csr_matrix, Dict[int, int], Dict[int, int], List[int], List[int], bool] = (
            self._create_mock_matrix_bundle(num_users=10)
        )
        self.mock_data_loader.build_user_item_matrix.return_value = matrix_bundle
        self.trainer.train_and_save_full_model()

        # Partial Fit 데이터: 사용자 수가 다름 (8명)
        partial_bundle: Tuple[csr_matrix, Dict[int, int], Dict[int, int], List[int], List[int], bool] = (
            self._create_mock_matrix_bundle(num_users=8, num_lectures=20)
        )
        matrix, u_to_idx, l_to_idx, users, lectures, _ = partial_bundle

        # is_new_user_added=False로 설정 (신규 사용자 없음)
        partial_bundle_modified: Tuple[csr_matrix, Dict[int, int], Dict[int, int], List[int], List[int], bool] = (
            matrix,
            u_to_idx,
            l_to_idx,
            users,
            lectures,
            False,
        )

        self.mock_data_loader.build_user_item_matrix.return_value = partial_bundle_modified

        # Partial Fit 실행
        result: bool = self.trainer.partial_fit_model_and_save()

        # Full Training으로 폴백되어야 함
        self.assertTrue(result)

    def test_partial_fit_old_lectures_none(self) -> None:
        """Partial Fit: old_lectures가 None인 경우 Full Training 폴백"""
        # 기존 모델 생성
        matrix_bundle: Tuple[csr_matrix, Dict[int, int], Dict[int, int], List[int], List[int], bool] = (
            self._create_mock_matrix_bundle(num_users=10)
        )
        self.mock_data_loader.build_user_item_matrix.return_value = matrix_bundle
        self.trainer.train_and_save_full_model()

        # 기존 모델 로드 후 old_lectures를 None으로 변경
        # Mock 객체가 아닌 실제 csr_matrix를 반환하도록 설정
        mock_model = Mock(spec=AlternatingLeastSquares)
        mock_matrix = self._create_mock_matrix_bundle(num_users=10)[0]  # 실제 csr_matrix

        with patch.object(self.trainer, "load_model_and_mappings") as mock_load:
            # old_lectures를 None으로 설정하되, matrix는 실제 객체 사용
            mock_load.return_value = (
                mock_model,
                {i: i for i in range(10)},
                {i: i for i in range(20)},
                list(range(10)),
                None,  # old_lectures = None
                mock_matrix,  # 실제 csr_matrix 사용
                timezone.now(),
            )

            # Partial Fit 데이터: 강의 수가 다름
            partial_bundle: Tuple[csr_matrix, Dict[int, int], Dict[int, int], List[int], List[int], bool] = (
                self._create_mock_matrix_bundle(num_users=10, num_lectures=15)
            )
            matrix, u_to_idx, l_to_idx, users, lectures, _ = partial_bundle

            partial_bundle_modified: Tuple[csr_matrix, Dict[int, int], Dict[int, int], List[int], List[int], bool] = (
                matrix,
                u_to_idx,
                l_to_idx,
                users,
                lectures,
                False,
            )

            self.mock_data_loader.build_user_item_matrix.return_value = partial_bundle_modified

            result: bool = self.trainer.partial_fit_model_and_save()

            # Full Training으로 폴백되어야 함
            self.assertTrue(result)

    def test_partial_fit_new_lectures_detected(self) -> None:
        """Partial Fit: 신규 강의 감지 시 Full Training 폴백"""
        # 기존 모델 생성 (강의 ID: 0-19)
        matrix_bundle: Tuple[csr_matrix, Dict[int, int], Dict[int, int], List[int], List[int], bool] = (
            self._create_mock_matrix_bundle(num_users=10, num_lectures=20)
        )
        self.mock_data_loader.build_user_item_matrix.return_value = matrix_bundle
        self.trainer.train_and_save_full_model()

        # Partial Fit 데이터: 신규 강의 ID 포함 (강의 ID: 20-24)
        np.random.seed(43)
        data: np.ndarray = np.random.rand(10 * 2)
        row: np.ndarray = np.random.randint(0, 10, 10 * 2)
        col: np.ndarray = np.random.randint(0, 5, 10 * 2)
        matrix: csr_matrix = csr_matrix((data, (row, col)), shape=(10, 5), dtype=np.float32)

        # 신규 강의 ID 사용 (20-24)
        new_lecture_ids: List[int] = list(range(20, 25))
        u_to_idx: Dict[int, int] = {i: i for i in range(10)}
        l_to_idx: Dict[int, int] = {lid: i for i, lid in enumerate(new_lecture_ids)}

        partial_bundle: Tuple[csr_matrix, Dict[int, int], Dict[int, int], List[int], List[int], bool] = (
            matrix,
            u_to_idx,
            l_to_idx,
            list(range(10)),
            new_lecture_ids,
            False,
        )

        self.mock_data_loader.build_user_item_matrix.return_value = partial_bundle

        result: bool = self.trainer.partial_fit_model_and_save()

        # Full Training으로 폴백되어야 함
        self.assertTrue(result)

    def test_partial_fit_implicit_library_error(self) -> None:
        """Partial Fit: implicit 라이브러리 에러 시 Full Training 폴백"""
        # 기존 모델 생성
        matrix_bundle: Tuple[csr_matrix, Dict[int, int], Dict[int, int], List[int], List[int], bool] = (
            self._create_mock_matrix_bundle(num_users=10)
        )
        self.mock_data_loader.build_user_item_matrix.return_value = matrix_bundle
        self.trainer.train_and_save_full_model()

        # Partial Fit 데이터
        partial_bundle: Tuple[csr_matrix, Dict[int, int], Dict[int, int], List[int], List[int], bool] = (
            self._create_mock_matrix_bundle(num_users=10, num_lectures=20)
        )
        matrix, u_to_idx, l_to_idx, users, lectures, _ = partial_bundle

        partial_bundle_modified: Tuple[csr_matrix, Dict[int, int], Dict[int, int], List[int], List[int], bool] = (
            matrix,
            u_to_idx,
            l_to_idx,
            users,
            lectures,
            False,
        )

        self.mock_data_loader.build_user_item_matrix.return_value = partial_bundle_modified

        # 원본 메서드를 패치 전에 저장
        original_load = self.trainer.load_model_and_mappings

        def mock_load_with_broken_model() -> Tuple[
            Optional[AlternatingLeastSquares],
            Optional[Dict[int, int]],
            Optional[Dict[int, int]],
            Optional[List[int]],
            Optional[List[int]],
            Optional[csr_matrix],
            Optional[datetime],
        ]:
            # 원본 메서드 호출 (패치되지 않은 버전)
            bundle = original_load()

            # 모델이 있으면 partial_fit_users를 에러 발생하도록 mock
            if bundle[0] is not None:
                bundle[0].partial_fit_users = Mock(side_effect=ValueError("Test error"))
                bundle[0].partial_fit_items = Mock(side_effect=ValueError("Test error"))

            return bundle

        with patch.object(
            self.trainer,
            "load_model_and_mappings",
            side_effect=mock_load_with_broken_model,
        ):
            result: bool = self.trainer.partial_fit_model_and_save()

            # Full Training으로 폴백되어야 함
            self.assertTrue(result)

    def test_partial_fit_lock_acquisition_failure(self) -> None:
        """Partial Fit: 락 획득 실패 시 False 반환"""
        # 기존 모델 생성
        matrix_bundle: Tuple[csr_matrix, Dict[int, int], Dict[int, int], List[int], List[int], bool] = (
            self._create_mock_matrix_bundle(num_users=10)
        )
        self.mock_data_loader.build_user_item_matrix.return_value = matrix_bundle
        self.trainer.train_and_save_full_model()

        # Partial Fit 데이터
        partial_bundle: Tuple[csr_matrix, Dict[int, int], Dict[int, int], List[int], List[int], bool] = (
            self._create_mock_matrix_bundle(num_users=10, num_lectures=20)
        )
        matrix, u_to_idx, l_to_idx, users, lectures, _ = partial_bundle

        partial_bundle_modified: Tuple[csr_matrix, Dict[int, int], Dict[int, int], List[int], List[int], bool] = (
            matrix,
            u_to_idx,
            l_to_idx,
            users,
            lectures,
            False,
        )

        self.mock_data_loader.build_user_item_matrix.return_value = partial_bundle_modified

        # 락 획득 실패 시뮬레이션
        with patch.object(self.trainer, "_acquire_lock_with_retry", return_value=False):
            result: bool = self.trainer.partial_fit_model_and_save()

            # False 반환되어야 함
            self.assertFalse(result)

    def test_partial_fit_cache_invalidation_on_success(self) -> None:
        """Partial Fit: 성공 시 캐시 무효화 확인"""
        # 기존 모델 생성
        matrix_bundle: Tuple[csr_matrix, Dict[int, int], Dict[int, int], List[int], List[int], bool] = (
            self._create_mock_matrix_bundle(num_users=10)
        )
        self.mock_data_loader.build_user_item_matrix.return_value = matrix_bundle
        self.trainer.train_and_save_full_model()

        # 캐시에 데이터 설정
        cache.set(ALS_MODEL_CACHE_KEY, "test_model")
        cache.set(U_TO_IDX_CACHE_KEY, {"1": 0})
        cache.set(L_TO_IDX_CACHE_KEY, {"1": 0})

        # Partial Fit 데이터
        partial_bundle: Tuple[csr_matrix, Dict[int, int], Dict[int, int], List[int], List[int], bool] = (
            self._create_mock_matrix_bundle(num_users=10, num_lectures=20)
        )
        matrix, u_to_idx, l_to_idx, users, lectures, _ = partial_bundle

        partial_bundle_modified: Tuple[csr_matrix, Dict[int, int], Dict[int, int], List[int], List[int], bool] = (
            matrix,
            u_to_idx,
            l_to_idx,
            users,
            lectures,
            False,
        )

        self.mock_data_loader.build_user_item_matrix.return_value = partial_bundle_modified

        result: bool = self.trainer.partial_fit_model_and_save()

        # 성공 확인
        self.assertTrue(result)

        # 캐시가 무효화되었는지 확인
        self.assertIsNone(cache.get(ALS_MODEL_CACHE_KEY))
        self.assertIsNone(cache.get(U_TO_IDX_CACHE_KEY))
        self.assertIsNone(cache.get(L_TO_IDX_CACHE_KEY))
        self.assertIsNone(cache.get(L_IDX_TO_ID_CACHE_KEY))
        self.assertIsNone(cache.get(USER_ITEMS_MATRIX_CACHE_KEY))

    def test_partial_fit_matrix_expansion(self) -> None:
        """Partial Fit: 행렬 확장 로직 테스트 (기존 강의 중 일부만 상호작용)"""
        # 기존 모델 생성 (10명 사용자, 20개 강의)
        matrix_bundle: Tuple[csr_matrix, Dict[int, int], Dict[int, int], List[int], List[int], bool] = (
            self._create_mock_matrix_bundle(num_users=10, num_lectures=20)
        )
        self.mock_data_loader.build_user_item_matrix.return_value = matrix_bundle
        self.trainer.train_and_save_full_model()

        # Partial Fit 데이터: 같은 사용자 수, 더 적은 강의 수 (15개)
        # 신규 강의는 없고, 기존 강의 중 일부만 상호작용 발생
        partial_bundle: Tuple[csr_matrix, Dict[int, int], Dict[int, int], List[int], List[int], bool] = (
            self._create_mock_matrix_bundle(num_users=10, num_lectures=15)
        )
        matrix, u_to_idx, l_to_idx, users, lectures, _ = partial_bundle

        # 기존 강의 ID 범위 내에서만 생성 (신규 강의 없음)
        lectures_subset = list(range(15))  # 0-14번 강의만 (기존 0-19번 중 일부)
        l_to_idx_subset = {l: i for i, l in enumerate(lectures_subset)}

        partial_bundle_modified: Tuple[csr_matrix, Dict[int, int], Dict[int, int], List[int], List[int], bool] = (
            matrix,
            u_to_idx,
            l_to_idx_subset,
            users,
            lectures_subset,
            False,
        )

        self.mock_data_loader.build_user_item_matrix.return_value = partial_bundle_modified

        result: bool = self.trainer.partial_fit_model_and_save()

        # 행렬 확장 로직이 성공적으로 실행되어야 함
        self.assertTrue(result)
