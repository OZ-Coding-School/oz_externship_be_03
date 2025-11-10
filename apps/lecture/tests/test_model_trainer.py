import os

os.environ["TQDM_DISABLE"] = "1"

import sys
from unittest.mock import MagicMock

sys.modules["tqdm"] = MagicMock()
sys.modules["tqdm.auto"] = MagicMock()
import logging
import shutil
import tempfile
import warnings
from datetime import datetime
from typing import Any, Dict, List, Optional
from unittest import mock

import joblib  # type: ignore
import numpy as np
from django.core.cache import cache
from django.utils import timezone
from scipy.sparse import csr_matrix # type: ignore

from apps.core.utils.isolated_cache_testcase import IsolatedRedisTestClient
from apps.lecture.services.recommendation_service.constants import (
    ALS_CACHE_KEYS,
    ALS_PARAMS,
    ALS_TRAINING_LOCK_KEY,
    LOCK_TIMEOUT_SECONDS,
    MAX_CACHE_LOAD_RETRIES,
)
from apps.lecture.services.recommendation_service.data_loader import DataLoader
from apps.lecture.services.recommendation_service.model_trainer import ModelTrainer


class DummyALSModel:
    """테스트용 직렬화 가능한 더미 ALS 모델"""

    def __init__(self) -> None:
        self.factors = 50
        self.regularization = 0.1
        self.iterations = 15
        self.user_factors: Optional[np.ndarray] = None
        self.item_factors: Optional[np.ndarray] = None

    def fit(self, matrix: csr_matrix) -> None:
        """간단한 랜덤 행렬로 학습 시뮬레이션"""
        self.user_factors = np.random.rand(matrix.shape[0], self.factors).astype(np.float32)
        self.item_factors = np.random.rand(matrix.shape[1], self.factors).astype(np.float32)

    def partial_fit_users(self, user_ids: np.ndarray, matrix: csr_matrix) -> None:
        """사용자 증분 학습 시뮬레이션"""
        if self.user_factors is None:
            self.user_factors = np.random.rand(len(user_ids), self.factors).astype(np.float32)

    def partial_fit_items(self, item_ids: np.ndarray, matrix: csr_matrix) -> None:
        """아이템 증분 학습 시뮬레이션"""
        if self.item_factors is None:
            self.item_factors = np.random.rand(len(item_ids), self.factors).astype(np.float32)


class ModelTrainerTestBase(IsolatedRedisTestClient):
    """ModelTrainer 테스트 Base 클래스"""

    MODEL_TRAINER_MODULE = "apps.lecture.services.recommendation_service.model_trainer"

    # 테스트 데이터 상수
    DEFAULT_USERS = [1, 2]
    DEFAULT_LECTURES = [10, 20]
    DEFAULT_MATRIX_DATA = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)

    # 추가 테스트 사용자/강의
    ADDITIONAL_USERS = [3, 4]
    ADDITIONAL_LECTURES = [30, 40]

    # 빈 데이터
    EMPTY_USERS: List[int] = []
    EMPTY_LECTURES: List[int] = []
    EMPTY_DICT: Dict[int, int] = {}

    @classmethod
    def setUpClass(cls) -> None:
        """클래스 레벨 설정"""
        super().setUpClass()

        logging.getLogger("apps.lecture.services.recommendation_service.model_trainer").setLevel(logging.CRITICAL + 1)
        logging.getLogger("apps.lecture.services.recommendation_service.recommender").setLevel(logging.CRITICAL + 1)
        logging.getLogger("apps.lecture.services.recommendation_service.data_loader").setLevel(logging.CRITICAL + 1)
        logging.getLogger("apps.lecture.tasks").setLevel(logging.CRITICAL + 1)

        # 외부 라이브러리 경고 억제
        warnings.filterwarnings("ignore", category=RuntimeWarning, module="implicit")
        warnings.filterwarnings("ignore", module="implicit.utils")

    def setUp(self) -> None:
        super().setUp()

        # IsolatedRedisTestClient의 CACHE_PREFIX 재사용 (UUID 기반)
        self.cache_prefix = self.CACHE_PREFIX

        # 프로세스별 고유 락 키 생성 (UUID prefix 사용)
        self.test_lock_key = f"{self.CACHE_PREFIX}{ALS_TRAINING_LOCK_KEY}"

        # 임시 모델 저장 디렉토리 생성 (UUID 사용)
        self.test_model_dir = tempfile.mkdtemp(prefix=f"als_test_{self.CACHE_PREFIX}_")
        self.addCleanup(shutil.rmtree, self.test_model_dir)

        # 테스트용 경로 설정
        self.test_bundle_path = os.path.join(self.test_model_dir, f"als_model_bundle_{ALS_PARAMS.factors}f_test.joblib")
        self.test_backup_path = self.test_bundle_path.replace(".joblib", "_backup.joblib")

        # Mock DataLoader 설정
        self.mock_data_loader = mock.MagicMock(spec=DataLoader)

        # Mock 패칭 설정
        self.model_dir_patcher = mock.patch(f"{self.MODEL_TRAINER_MODULE}.MODEL_DIR", self.test_model_dir)
        self.bundle_path_patcher = mock.patch(f"{self.MODEL_TRAINER_MODULE}.MODEL_BUNDLE_PATH", self.test_bundle_path)
        self.backup_path_patcher = mock.patch(f"{self.MODEL_TRAINER_MODULE}.MODEL_BACKUP_PATH", self.test_backup_path)

        self.model_dir_patcher.start()
        self.bundle_path_patcher.start()
        self.backup_path_patcher.start()

        self.addCleanup(self.model_dir_patcher.stop)
        self.addCleanup(self.bundle_path_patcher.stop)
        self.addCleanup(self.backup_path_patcher.stop)

        # UUID prefix 기반 캐시 키 초기화
        cache.delete_many(
            [
                self.test_lock_key,
                *[f"{self.CACHE_PREFIX}{key}" for key in ALS_CACHE_KEYS],
            ]
        )

        # ModelTrainer 인스턴스 생성 (락 키를 생성자에 주입)
        self.trainer = ModelTrainer(self.mock_data_loader, lock_key=self.test_lock_key)

    def tearDown(self) -> None:
        """각 테스트 후 실행: UUID prefix 기반 캐시 키만 정리"""
        # UUID prefix 기반 캐시 키만 삭제
        cache.delete_many(
            [
                self.test_lock_key,
                *[f"{self.CACHE_PREFIX}{key}" for key in ALS_CACHE_KEYS],
            ]
        )
        super().tearDown()

    def _create_test_model_bundle(
        self,
        users: Optional[List[int]] = None,
        lectures: Optional[List[int]] = None,
        matrix_data: Optional[np.ndarray] = None,
        last_trained_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """테스트용 모델 번들 생성 헬퍼 (상수 사용)"""
        if users is None:
            users = self.DEFAULT_USERS
        if lectures is None:
            lectures = self.DEFAULT_LECTURES
        if matrix_data is None:
            matrix_data = self.DEFAULT_MATRIX_DATA
        if last_trained_at is None:
            last_trained_at = timezone.now()

        model = DummyALSModel()
        test_matrix = csr_matrix(matrix_data)

        return {
            "model": model,
            "user_to_idx": {u: i for i, u in enumerate(users)},
            "lecture_to_idx": {l: i for i, l in enumerate(lectures)},
            "users": users,
            "lectures": lectures,
            "matrix": test_matrix,
            "last_trained_at": last_trained_at,
        }

    def _create_and_save_model(
        self,
        users: Optional[List[int]] = None,
        lectures: Optional[List[int]] = None,
        matrix_data: Optional[np.ndarray] = None,
    ) -> None:
        """모델 생성 및 저장 헬퍼"""
        data = self._create_test_model_bundle(users=users, lectures=lectures, matrix_data=matrix_data)
        joblib.dump(data, self.test_bundle_path)

    def _assert_lock_released(self) -> None:
        """락 해제 확인 헬퍼"""
        self.assertIsNone(cache.get(self.test_lock_key), "Lock should be released")


class ModelTrainerCacheTestCase(ModelTrainerTestBase):
    """캐시 관리 테스트"""

    def test_clear_redis_cache_success(self) -> None:
        """캐시 키 삭제 성공 테스트"""
        # Given: 캐시에 데이터 설정
        for key in ALS_CACHE_KEYS:
            cache.set(key, "test_value", timeout=60)

        # When: 캐시 삭제
        self.trainer._clear_redis_cache()

        # Then: 모든 캐시 키가 삭제됨
        for key in ALS_CACHE_KEYS:
            self.assertIsNone(cache.get(key), f"Cache key {key} should be deleted")

    def test_clear_redis_cache_handles_exception(self) -> None:
        """캐시 삭제 실패 시 예외 처리 테스트"""
        # Given: cache.delete_many가 실패하도록 설정
        with mock.patch.object(cache, "delete_many", side_effect=Exception("Redis connection error")):
            # When/Then: 예외가 발생하지 않아야 함
            try:
                self.trainer._clear_redis_cache()
            except Exception as e:
                self.fail(f"_clear_redis_cache should not raise exception: {e}")


class ModelTrainerStorageTestCase(ModelTrainerTestBase):
    """모델 저장/로드 테스트"""

    def test_safe_dump_model_success(self) -> None:
        """모델 정상 저장 테스트 (atomic write)"""
        # Given: 테스트 모델 번들
        test_obj = self._create_test_model_bundle()

        # When: 모델 저장
        result = self.trainer._safe_dump_model(test_obj)

        # Then: 저장 성공 및 파일 존재 확인
        self.assertTrue(result, "Model save should succeed")
        self.assertTrue(os.path.exists(self.test_bundle_path), "Model file should exist")

    def test_safe_dump_model_with_existing_file(self) -> None:
        """기존 파일이 있을 때 모델 저장 테스트"""
        # Given: 기존 파일 생성
        existing_data = self._create_test_model_bundle()
        joblib.dump(existing_data, self.test_bundle_path)

        # When: 새 데이터로 저장
        new_data = self._create_test_model_bundle(users=self.ADDITIONAL_USERS, lectures=self.ADDITIONAL_LECTURES)
        result = self.trainer._safe_dump_model(new_data)

        # Then: 저장 성공
        self.assertTrue(result, "Model save should succeed with existing file")

    def test_safe_dump_model_recovery_on_failure(self) -> None:
        """저장 실패 시 백업에서 복구 테스트"""
        # Given: 기존 파일 생성
        existing_data = self._create_test_model_bundle()
        joblib.dump(existing_data, self.test_bundle_path)

        test_obj = self._create_test_model_bundle(users=[3, 4])

        # When: 저장 실패 시뮬레이션 (joblib.dump 실패)
        with mock.patch("joblib.dump", side_effect=Exception("Disk full")):
            result = self.trainer._safe_dump_model(test_obj)

        # Then: 저장 실패하지만 기존 파일은 백업에서 복구됨
        self.assertFalse(result, "Save should fail")
        self.assertTrue(os.path.exists(self.test_bundle_path), "Original file should be restored from backup")
        loaded_data = joblib.load(self.test_bundle_path)
        self.assertEqual(loaded_data["users"], existing_data["users"], "Data should be restored from backup")

    def test_safe_dump_model_clears_cache_on_success(self) -> None:
        """저장 성공 시 캐시 무효화 테스트"""
        # Given: 캐시에 데이터 설정
        for key in ALS_CACHE_KEYS:
            cache.set(key, "old_value", timeout=60)

        test_obj = self._create_test_model_bundle()

        # When: 모델 저장
        self.trainer._safe_dump_model(test_obj)

        # Then: 캐시가 삭제되었는지 확인
        for key in ALS_CACHE_KEYS:
            self.assertIsNone(cache.get(key), f"Cache key {key} should be cleared")

    def test_safe_dump_model_logs_metadata(self) -> None:
        """메타데이터 로깅 테스트"""
        # Given: 테스트 모델 번들
        test_obj = self._create_test_model_bundle()

        # When: 모델 저장 (로그 캡처)
        with self.assertLogs(self.MODEL_TRAINER_MODULE, level="INFO") as cm:
            self.trainer._safe_dump_model(test_obj)

        # Then: 로그 메시지 확인
        self.assertTrue(
            any("Model saved atomically" in msg or "ALS" in msg for msg in cm.output),
            "Should log save message",
        )

    def test_load_model_and_mappings_success(self) -> None:
        """모델 정상 로드 테스트"""
        # Given: 테스트 모델 파일 생성
        test_data = self._create_test_model_bundle(
            users=[self.DEFAULT_USERS[0]],  # 첫 번째 사용자만
            lectures=[self.DEFAULT_LECTURES[0]],  # 첫 번째 강의만
            last_trained_at=datetime(2024, 1, 1, 12, 0, 0),
        )
        joblib.dump(test_data, self.test_bundle_path)

        # When: 모델 로드
        result = self.trainer.load_model_and_mappings()

        # Then: 로드 성공 및 timezone-aware 변환 확인
        model, u_to_i, l_to_i, users, lectures, matrix, last_trained_at = result
        self.assertIsNotNone(model, "Model should be loaded")
        self.assertEqual(u_to_i, {self.DEFAULT_USERS[0]: 0})
        self.assertEqual(l_to_i, {self.DEFAULT_LECTURES[0]: 0})
        self.assertEqual(users, [self.DEFAULT_USERS[0]])
        self.assertEqual(lectures, [self.DEFAULT_LECTURES[0]])

        assert last_trained_at is not None
        self.assertIsNotNone(last_trained_at.tzinfo, "Should be timezone-aware")

    def test_load_model_and_mappings_errors(self) -> None:
        """모델 로드 에러 시나리오 통합 테스트 (parametrized)"""
        test_cases = [
            ("file_not_found", "non_existent.joblib", None),
            ("corrupted_file", self.test_bundle_path, b"corrupted"),
        ]

        for name, path, setup in test_cases:
            with self.subTest(scenario=name):
                # Setup
                if setup == b"corrupted":
                    with open(path, "wb") as f:
                        f.write(setup)

                # When
                if name == "file_not_found":
                    with mock.patch(f"{self.MODEL_TRAINER_MODULE}.MODEL_BUNDLE_PATH", path):
                        result = self.trainer.load_model_and_mappings()
                else:
                    result = self.trainer.load_model_and_mappings()

                # Then
                self.assertEqual(result, (None, None, None, None, None, None, None))

    def test_load_model_and_mappings_permission_error(self) -> None:
        """권한 오류 테스트"""
        # Given: 파일 생성 후 읽기 권한 제거
        joblib.dump({"test": "data"}, self.test_bundle_path)
        os.chmod(self.test_bundle_path, 0o000)
        self.addCleanup(lambda: os.chmod(self.test_bundle_path, 0o644))

        # When: 모델 로드 시도
        result = self.trainer.load_model_and_mappings()

        # Then: 모두 None 반환
        self.assertEqual(result, (None, None, None, None, None, None, None))


class ModelTrainerLockTestCase(ModelTrainerTestBase):
    """락 획득 관련 테스트"""

    def test_acquire_lock_with_retry_success_first_attempt(self) -> None:
        """첫 시도에 락 획득 성공 테스트"""
        # Given: 락이 없는 상태
        cache.delete(self.test_lock_key)

        # When: 락 획득 시도
        result = self.trainer._acquire_lock_with_retry(self.test_lock_key, LOCK_TIMEOUT_SECONDS)

        # Then: 성공
        self.assertTrue(result, "Lock should be acquired on first attempt")
        self.assertIsNotNone(cache.get(self.test_lock_key))

    def test_acquire_lock_with_retry_max_retries(self) -> None:
        """최대 재시도 횟수 테스트 (sleep mock으로 시간 단축)"""
        # Given: 락이 계속 존재
        cache.set(self.test_lock_key, True, timeout=LOCK_TIMEOUT_SECONDS)

        # When: 락 획득 시도 (sleep을 mock하여 테스트 시간 단축)
        with mock.patch("time.sleep"):
            result = self.trainer._acquire_lock_with_retry(self.test_lock_key, LOCK_TIMEOUT_SECONDS)

        # Then: 실패
        self.assertFalse(result, "Lock acquisition should fail after max retries")

    def test_acquire_lock_with_retry_handles_cache_exception(self) -> None:
        """캐시 예외 처리 테스트"""
        # Given: cache.add가 예외 발생하도록 설정
        with mock.patch.object(cache, "add", side_effect=Exception("Redis error")):
            # When: 락 획득 시도
            with mock.patch("time.sleep"):
                result = self.trainer._acquire_lock_with_retry(self.test_lock_key, LOCK_TIMEOUT_SECONDS)

        # Then: 실패
        self.assertFalse(result, "Should fail gracefully on cache exception")

    def test_acquire_lock_with_retry_exact_retries(self) -> None:
        """정확히 5회 재시도 확인 (경계값 테스트)"""
        # Given: 락이 계속 존재
        cache.set(self.test_lock_key, True, timeout=LOCK_TIMEOUT_SECONDS)

        # When: 락 획득 시도
        with mock.patch("time.sleep") as mock_sleep:
            result = self.trainer._acquire_lock_with_retry(self.test_lock_key, LOCK_TIMEOUT_SECONDS)

        # Then: 첫 시도는 sleep 없음, 이후 4번 재시도에서 sleep 호출
        self.assertEqual(mock_sleep.call_count, MAX_CACHE_LOAD_RETRIES - 1)
        self.assertFalse(result)


class ModelTrainerFullTrainingTestCase(ModelTrainerTestBase):
    """전체 학습 관련 테스트"""

    def test_train_and_save_full_model_success(self) -> None:
        """전체 모델 정상 학습 테스트"""
        # Given: 테스트 데이터 설정
        test_matrix = csr_matrix(self.DEFAULT_MATRIX_DATA)
        self.mock_data_loader.build_user_item_matrix.return_value = (
            test_matrix,
            {1: 0, 2: 1},
            {10: 0, 20: 1},
            self.DEFAULT_USERS,
            self.DEFAULT_LECTURES,
            False,
        )

        # When: 전체 모델 학습
        result = self.trainer.train_and_save_full_model()

        # Then: 성공
        self.assertTrue(result)
        self.assertTrue(os.path.exists(self.test_bundle_path))

    def test_train_and_save_full_model_no_data(self) -> None:
        """데이터 없을 때 테스트"""
        # Given: 빈 행렬
        empty_matrix = csr_matrix((0, 0), dtype=np.float32)  # type: ignore[type-var]
        self.mock_data_loader.build_user_item_matrix.return_value = (
            empty_matrix,
            {},
            {},
            [],
            [],
            False,
        )

        # When: 전체 모델 학습
        result = self.trainer.train_and_save_full_model()

        # Then: 성공 (빈 모델도 저장 가능)
        self.assertTrue(result, "Training should succeed even with empty data")

    def test_train_and_save_full_model_lock_acquisition_failure(self) -> None:
        """락 획득 실패 테스트"""
        # Given: 락이 이미 존재 (프로세스별 키 사용)
        cache.set(self.test_lock_key, True, timeout=LOCK_TIMEOUT_SECONDS)

        # 상수 사용으로 변경
        test_matrix = csr_matrix(self.DEFAULT_MATRIX_DATA)
        self.mock_data_loader.build_user_item_matrix.return_value = (
            test_matrix,
            {self.DEFAULT_USERS[0]: 0},
            {self.DEFAULT_LECTURES[0]: 0},
            [self.DEFAULT_USERS[0]],
            [self.DEFAULT_LECTURES[0]],
            False,
        )

        # When: 전체 모델 학습 시도 (sleep mock으로 시간 단축)
        with mock.patch("time.sleep"):
            result = self.trainer.train_and_save_full_model()

            # Then: 실패
        self.assertFalse(result, "Should fail when lock cannot be acquired")

    def test_train_and_save_full_model_releases_lock_on_success(self) -> None:
        """학습 성공 후 락 해제 테스트"""
        # Given: Mock 데이터 로더 설정
        test_matrix = csr_matrix(np.array([[1.0]], dtype=np.float32))
        self.mock_data_loader.build_user_item_matrix.return_value = (test_matrix, {1: 0}, {10: 0}, [1], [10], False)

        # When: 전체 모델 학습
        self.trainer.train_and_save_full_model()

        # Then: 락이 해제되었는지 확인
        self._assert_lock_released()

    def test_train_and_save_full_model_logs_metadata(self) -> None:
        """메타데이터 로깅 테스트"""
        # Given: Mock 데이터 로더 설정
        test_matrix = csr_matrix(np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32))
        self.mock_data_loader.build_user_item_matrix.return_value = (
            test_matrix,
            {1: 0, 2: 1},
            {10: 0, 20: 1},
            [1, 2],
            [10, 20],
            False,
        )

        # When: 전체 모델 학습 (로그 캡처)
        with self.assertLogs(self.MODEL_TRAINER_MODULE, level="INFO") as cm:
            self.trainer.train_and_save_full_model()

        # Then: ALS 관련 로그 확인
        self.assertTrue(any("ALS" in msg for msg in cm.output), "Should log ALS-related messages")


class ModelTrainerPartialTrainingTestCase(ModelTrainerTestBase):
    """증분 학습 관련 테스트"""

    def test_partial_fit_model_and_save_success(self) -> None:
        """증분 학습 정상 동작 테스트"""
        # Given: 기존 모델 파일 생성
        self._create_and_save_model()

        # 신규 데이터 설정
        new_matrix = csr_matrix(np.array([[0.5, 0.0], [0.0, 0.5]], dtype=np.float32))
        self.mock_data_loader.build_user_item_matrix.return_value = (
            new_matrix,
            {1: 0, 2: 1},
            {10: 0, 20: 1},
            [1, 2],
            [10, 20],
            False,
        )

        # When: 증분 학습
        result = self.trainer.partial_fit_model_and_save()

        # Then: 성공
        self.assertTrue(result)

    def test_partial_fit_model_and_save_no_base_model(self) -> None:
        """기존 모델 없을 때 Full Training 폴백 테스트"""
        # Given: 모델 파일 없음
        # When: 증분 학습 시도
        with mock.patch.object(self.trainer, "train_and_save_full_model", return_value=True) as mock_full_train:
            result = self.trainer.partial_fit_model_and_save()

        # Then: Full Training 호출됨
        mock_full_train.assert_called_once()
        self.assertTrue(result)

    def test_partial_fit_model_and_save_new_user_detected(self) -> None:
        """신규 사용자 감지 시 Full Training 폴백 테스트"""
        # Given: 기존 모델 파일 생성
        self._create_and_save_model()

        # 신규 사용자 추가된 데이터
        new_users = self.DEFAULT_USERS + [self.ADDITIONAL_USERS[0]]  # 신규 사용자 추가
        new_matrix = csr_matrix(np.array([[1.0, 0.0]], dtype=np.float32))
        self.mock_data_loader.build_user_item_matrix.return_value = (
            new_matrix,
            {new_users[0]: 0},
            {self.DEFAULT_LECTURES[0]: 0},
            [new_users[0]],
            [self.DEFAULT_LECTURES[0]],
            True,  # is_new_user_added = True
        )

        # When: 증분 학습 시도 (로그 캡처)
        with self.assertLogs(self.MODEL_TRAINER_MODULE, level="WARNING") as cm:
            with mock.patch.object(self.trainer, "train_and_save_full_model", return_value=True) as mock_full_train:
                result = self.trainer.partial_fit_model_and_save()

        # Then: 경고 로그 및 Full Training 호출 확인
        self.assertTrue(any("New user(s) detected" in msg for msg in cm.output), "Should log warning about new users")
        mock_full_train.assert_called_once()
        self.assertTrue(result)

    def test_partial_fit_model_and_save_new_lecture_detected(self) -> None:
        """신규 강의 감지 시 Full Training 폴백 테스트"""
        # Given: 기존 모델 파일 생성
        self._create_and_save_model()

        # 신규 강의 포함 데이터 설정
        new_matrix = csr_matrix(np.array([[0.5, 0.0, 0.3], [0.0, 0.5, 0.2]], dtype=np.float32))
        self.mock_data_loader.build_user_item_matrix.return_value = (
            new_matrix,
            {1: 0, 2: 1},
            {10: 0, 20: 1, 30: 2},  # 신규 강의 30 추가
            [1, 2],
            [10, 20, 30],
            True,
        )

        # When: 증분 학습 시도
        with mock.patch.object(self.trainer, "train_and_save_full_model", return_value=True) as mock_full_train:
            result = self.trainer.partial_fit_model_and_save()

        # Then: Full Training 호출
        mock_full_train.assert_called_once()
        self.assertTrue(result)

    def test_partial_fit_model_and_save_shape_mismatch(self) -> None:
        """Shape 불일치 시 Full Training 폴백 테스트"""
        # Given: 기존 모델 파일 생성
        self._create_and_save_model(
            users=[1, 2], lectures=[10, 20], matrix_data=np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
        )

        # Shape 불일치 데이터 (사용자 수 다름)
        new_matrix = csr_matrix(np.array([[1.0, 0.0]], dtype=np.float32))
        self.mock_data_loader.build_user_item_matrix.return_value = (
            new_matrix,
            {1: 0},
            {10: 0, 20: 1},
            [1],
            [10, 20],
            False,
        )

        # When: 증분 학습 시도
        with mock.patch.object(self.trainer, "train_and_save_full_model", return_value=True) as mock_full_train:
            result = self.trainer.partial_fit_model_and_save()

            # Then: Full Training 호출됨
        mock_full_train.assert_called_once()
        self.assertTrue(result)

    def test_partial_fit_model_and_save_no_new_data(self) -> None:
        """신규 데이터 없을 때 학습 스킵 테스트"""
        # Given: 기존 모델 파일 생성
        self._create_and_save_model()

        # 신규 데이터 없음
        self.mock_data_loader.build_user_item_matrix.return_value = None

        # When: 증분 학습 시도
        result = self.trainer.partial_fit_model_and_save()

        # Then: True 반환
        self.assertTrue(result)

    def test_partial_fit_model_and_save_partial_fit_failure(self) -> None:
        """implicit partial_fit 실패 시 Full Training 폴백 테스트"""
        # Given: 기존 모델 파일 생성
        self._create_and_save_model()

        # 신규 데이터 설정
        new_matrix = csr_matrix(np.array([[0.5, 0.0], [0.0, 0.5]], dtype=np.float32))
        self.mock_data_loader.build_user_item_matrix.return_value = (
            new_matrix,
            {1: 0, 2: 1},
            {10: 0, 20: 1},
            [1, 2],
            [10, 20],
            False,
        )

        # When: 증분 학습 시도
        with mock.patch.object(DummyALSModel, "partial_fit_users", side_effect=Exception("Implicit error")):
            with mock.patch.object(self.trainer, "train_and_save_full_model", return_value=True) as mock_full_train:
                result = self.trainer.partial_fit_model_and_save()

        # Then: Full Training 호출
        mock_full_train.assert_called_once()
        self.assertTrue(result)

    def test_partial_fit_model_and_save_releases_lock(self) -> None:
        """증분 학습 후 락 해제 테스트"""
        # Given: 기존 모델 파일 생성
        self._create_and_save_model()

        # 신규 데이터 설정
        new_matrix = csr_matrix(np.array([[0.5, 0.0], [0.0, 0.5]], dtype=np.float32))
        self.mock_data_loader.build_user_item_matrix.return_value = (
            new_matrix,
            {1: 0, 2: 1},
            {10: 0, 20: 1},
            [1, 2],
            [10, 20],
            False,
        )

        # When: 증분 학습
        self.trainer.partial_fit_model_and_save()

        # Then: 락이 해제되었는지 확인
        self._assert_lock_released()

    def test_partial_fit_model_and_save_matrix_expansion(self) -> None:
        """부분 행렬 확장 테스트 (신규 강의 없지만 shape 다른 경우)"""
        # Given: 기존 모델 파일 생성
        self._create_and_save_model(
            users=[1, 2],
            lectures=[10, 20, 30],
            matrix_data=np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float32),
        )

        # 부분 행렬 (일부 강의만 상호작용 발생)
        new_matrix = csr_matrix(np.array([[0.5, 0.0], [0.0, 0.5]], dtype=np.float32))
        self.mock_data_loader.build_user_item_matrix.return_value = (
            new_matrix,
            {1: 0, 2: 1},
            {10: 0, 20: 1},  # 강의 30 없음
            [1, 2],
            [10, 20],
            False,
        )

        # When: 증분 학습
        result = self.trainer.partial_fit_model_and_save()

        # Then: 성공 (행렬 확장 처리됨)
        self.assertTrue(result)


class ModelTrainerBoundaryTestCase(ModelTrainerTestBase):
    """경계값 테스트"""

    def test_train_and_save_full_model_empty_matrix(self) -> None:
        """빈 행렬 경계값 테스트"""
        # Given: 0x0 행렬
        test_matrix = csr_matrix(  # type: ignore[type-var]
            (
                np.array([], dtype=np.float32),
                (np.array([], dtype=np.int32), np.array([], dtype=np.int32)),
            ),
            shape=(0, 0),
            dtype=np.float32,
        )
        self.mock_data_loader.build_user_item_matrix.return_value = (
            test_matrix,
            self.EMPTY_DICT,
            self.EMPTY_DICT,
            self.EMPTY_USERS,
            self.EMPTY_LECTURES,
            False,
        )

        # When: 전체 모델 학습
        result = self.trainer.train_and_save_full_model()

        # Then: 성공 (빈 모델도 저장 가능)
        self.assertTrue(result, "Empty matrix training should succeed")

    def test_acquire_lock_with_retry_exact_retries(self) -> None:
        """정확히 5회 재시도 확인 (경계값 테스트)"""
        # Given: 락이 계속 존재
        cache.set(self.test_lock_key, True, timeout=LOCK_TIMEOUT_SECONDS)

        # When: 락 획득 시도
        with mock.patch("time.sleep") as mock_sleep:
            result = self.trainer._acquire_lock_with_retry(self.test_lock_key, LOCK_TIMEOUT_SECONDS)

        # Then: 정확히 4회 sleep 호출 (첫 시도는 sleep 없음, 이후 4번 재시도)
        self.assertEqual(mock_sleep.call_count, MAX_CACHE_LOAD_RETRIES - 1, "Should retry exactly 4 times")
        self.assertFalse(result, "Lock acquisition should fail after max retries")
