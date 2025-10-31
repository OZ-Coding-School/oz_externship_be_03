import os
import tempfile
from collections import namedtuple
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock, patch

import joblib  # type: ignore
import numpy as np
from django.core.cache import cache
from django.utils import timezone
from implicit.als import AlternatingLeastSquares  # type: ignore
from scipy.sparse import csr_matrix

from apps.core.utils.isolated_cache_testcase import IsolatedRedisTestClient
from apps.lecture.services.recommendation_service.constants import (
    ALS_MODEL_CACHE_KEY,
    ALS_PARAMS,
    ALS_TRAINING_LOCK_KEY,
    L_TO_IDX_CACHE_KEY,
    MAX_CACHE_LOAD_RETRIES,
    U_TO_IDX_CACHE_KEY,
)
from apps.lecture.services.recommendation_service.data_loader import DataLoader
from apps.lecture.services.recommendation_service.model_trainer import ModelTrainer


class ModelBundleFactory:
    """테스트 데이터 생성 헬퍼"""

    ModelBundle = namedtuple(
        "ModelBundle", ["model", "user_to_idx", "lecture_to_idx", "users", "lectures", "matrix", "last_trained_at"]
    )

    MatrixBundle = namedtuple(
        "MatrixBundle", ["matrix", "user_to_idx", "lecture_to_idx", "users", "lectures", "is_new_user_added"]
    )

    @staticmethod
    def create_model_bundle(
        model: Optional[Any] = None,
        user_to_idx: Optional[Dict[int, int]] = None,
        lecture_to_idx: Optional[Dict[int, int]] = None,
        users: Optional[List[int]] = None,
        lectures: Optional[List[int]] = None,
        matrix: Optional[csr_matrix] = None,
        last_trained_at: Optional[datetime] = None,
    ) -> "ModelBundleFactory.ModelBundle":
        """모델 번들 생성

        기본값:
        - model: MagicMock(spec=AlternatingLeastSquares)
        - user_to_idx: {1: 0}
        - lecture_to_idx: {10: 0}
        - users: [1]
        - lectures: [10]
        - matrix: 1x1 희소 행렬
        - last_trained_at: 1일 전
        """
        return ModelBundleFactory.ModelBundle(
            model=model or MagicMock(spec=AlternatingLeastSquares),
            user_to_idx=user_to_idx or {1: 0},
            lecture_to_idx=lecture_to_idx or {10: 0},
            users=users or [1],
            lectures=lectures or [10],
            matrix=matrix if matrix is not None else csr_matrix(np.array([[1.0]], dtype=np.float32)),
            last_trained_at=last_trained_at or (timezone.now() - timedelta(days=1)),
        )

    @staticmethod
    def create_matrix_bundle(
        matrix: Optional[csr_matrix] = None,
        user_to_idx: Optional[Dict[int, int]] = None,
        lecture_to_idx: Optional[Dict[int, int]] = None,
        users: Optional[List[int]] = None,
        lectures: Optional[List[int]] = None,
        is_new_user_added: bool = False,
    ) -> "ModelBundleFactory.MatrixBundle":
        """
        행렬 번들 생성 (DataLoader.build_user_item_matrix 반환값)

        기본값:
        - matrix: 1x1 희소 행렬
        - user_to_idx: {1: 0}
        - lecture_to_idx: {10: 0}
        - users: [1]
        - lectures: [10]
        - is_new_user_added: False
        """
        return ModelBundleFactory.MatrixBundle(
            matrix=matrix if matrix is not None else csr_matrix(np.array([[1.0]], dtype=np.float32)),
            user_to_idx=user_to_idx or {1: 0},
            lecture_to_idx=lecture_to_idx or {10: 0},
            users=users or [1],
            lectures=lectures or [10],
            is_new_user_added=is_new_user_added,
        )


class ModelTrainerInitTests(IsolatedRedisTestClient):
    """ModelTrainer 초기화 및 캐시 관리 테스트"""

    def setUp(self) -> None:
        super().setUp()
        self.temp_dir: "tempfile.TemporaryDirectory[str]" = tempfile.TemporaryDirectory()
        self.data_loader: DataLoader = DataLoader()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()
        super().tearDown()

    def test_init_creates_model_directory(self) -> None:
        """초기화 시 MODEL_DIR 생성 검증
        - os.makedirs(MODEL_DIR, exist_ok=True) 호출 확인
        - 하이퍼파라미터 로드 확인
        """
        with patch("apps.lecture.services.recommendation_service.model_trainer.MODEL_DIR", self.temp_dir.name):
            trainer: ModelTrainer = ModelTrainer(self.data_loader)

            self.assertTrue(os.path.exists(self.temp_dir.name))
            self.assertEqual(trainer.params, ALS_PARAMS)

    def test_clear_redis_cache_deletes_all_keys(self) -> None:
        """_clear_redis_cache가 모든 ALS 캐시 키 삭제 검증
        - cache.delete_many(ALS_CACHE_KEYS) 호출
        - 모든 키가 삭제되었는지 확인
        """
        # Given: 캐시에 데이터 저장
        cache.set(ALS_MODEL_CACHE_KEY, "test_model")
        cache.set(U_TO_IDX_CACHE_KEY, {"1": 0})
        cache.set(L_TO_IDX_CACHE_KEY, {"1": 0})

        # When: 캐시 삭제
        trainer: ModelTrainer = ModelTrainer(self.data_loader)
        trainer._clear_redis_cache()

        # Then: 모든 키 삭제 확인
        self.assertIsNone(cache.get(ALS_MODEL_CACHE_KEY))
        self.assertIsNone(cache.get(U_TO_IDX_CACHE_KEY))
        self.assertIsNone(cache.get(L_TO_IDX_CACHE_KEY))

    def test_clear_redis_cache_handles_exception(self) -> None:
        """캐시 삭제 실패 시 에러 로깅하지만 프로세스 계속 검증
        - 예외 발생해도 프로그램 중단 안됨
        """
        trainer: ModelTrainer = ModelTrainer(self.data_loader)

        with patch.object(cache, "delete_many", side_effect=Exception("Cache error")):
            # 예외 발생해도 정상 실행
            trainer._clear_redis_cache()


class ModelTrainerSafeDumpTests(IsolatedRedisTestClient):
    """ModelTrainer atomic 파일 저장 테스트"""

    def setUp(self) -> None:
        super().setUp()
        self.temp_dir: "tempfile.TemporaryDirectory[str]" = tempfile.TemporaryDirectory()
        self.data_loader: DataLoader = DataLoader()
        self.trainer: ModelTrainer = ModelTrainer(self.data_loader)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()
        super().tearDown()

    def test_safe_dump_model_success(self) -> None:
        """정상 저장 (atomic 파일 교체) 테스트
        - 임시 파일 생성 -> 원자적 교체 -> 백업 삭제
        """
        bundle_path: str = os.path.join(self.temp_dir.name, "model.joblib")
        test_matrix: csr_matrix = csr_matrix(np.array([[1.0]], dtype=np.float32))

        # 실제 ALS 모델 생성 (pickle 가능)
        real_model: AlternatingLeastSquares = AlternatingLeastSquares(factors=5, iterations=1)

        obj: Dict[str, Any] = {
            "model": real_model,
            "user_to_idx": {1: 0},
            "lecture_to_idx": {10: 0},
            "users": [1],
            "lectures": [10],
            "matrix": test_matrix,
            "last_trained_at": timezone.now(),
        }

        with patch(
            "apps.lecture.services.recommendation_service.model_trainer.MODEL_BUNDLE_PATH",
            bundle_path,
        ):
            result: bool = self.trainer._safe_dump_model(obj)

        self.assertTrue(result)
        self.assertTrue(os.path.exists(bundle_path))


class ModelTrainerLoadTests(IsolatedRedisTestClient):
    """ModelTrainer 모델 로드 테스트"""

    def setUp(self) -> None:
        super().setUp()
        self.temp_dir: "tempfile.TemporaryDirectory[str]" = tempfile.TemporaryDirectory()
        self.data_loader: DataLoader = DataLoader()
        self.trainer: ModelTrainer = ModelTrainer(self.data_loader)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()
        super().tearDown()

    def test_load_model_returns_none_when_file_not_exists(self) -> None:
        """파일 없을 시 None 튜플 반환
        - 모든 반환값이 None
        """
        with patch(
            "apps.lecture.services.recommendation_service.model_trainer.MODEL_BUNDLE_PATH",
            "/nonexistent/path.joblib",
        ):
            result = self.trainer.load_model_and_mappings()

            # 모든 값이 None인지 확인
            self.assertIsNotNone(result)
            if result is not None:
                model, u_to_idx, l_to_idx, users, lectures, matrix, last_trained_at = result
                self.assertIsNone(model)
                self.assertIsNone(u_to_idx)
                self.assertIsNone(l_to_idx)
                self.assertIsNone(users)
                self.assertIsNone(lectures)
                self.assertIsNone(matrix)
                self.assertIsNone(last_trained_at)

    def test_load_model_converts_naive_datetime_to_aware(self) -> None:
        """naive datetime을 timezone-aware로 변환 테스트
        - tzinfo가 None이면 timezone.make_aware 호출
        """
        bundle_path: str = os.path.join(self.temp_dir.name, "model.joblib")

        naive_dt: datetime = datetime(2024, 1, 1, 12, 0, 0)  # naive datetime

        bundle = ModelBundleFactory.create_model_bundle(
            model=AlternatingLeastSquares(factors=5, iterations=1),
            last_trained_at=naive_dt,
        )

        joblib.dump(bundle._asdict(), bundle_path)

        with patch(
            "apps.lecture.services.recommendation_service.model_trainer.MODEL_BUNDLE_PATH",
            bundle_path,
        ):
            result = self.trainer.load_model_and_mappings()

        # timezone-aware로 변환되었는지 확인
        self.assertIsNotNone(result)
        if result is not None:
            _, _, _, _, _, _, last_trained_at = result
            self.assertIsNotNone(last_trained_at)
            if last_trained_at is not None:
                self.assertIsNotNone(last_trained_at.tzinfo)


class ModelTrainerLockTests(IsolatedRedisTestClient):
    """ModelTrainer Redis 락 획득 테스트"""

    def setUp(self) -> None:
        super().setUp()
        self.data_loader: DataLoader = DataLoader()
        self.trainer: ModelTrainer = ModelTrainer(self.data_loader)

    def test_acquire_lock_success_on_first_try(self) -> None:
        """첫 시도에 락 획득 성공
        - cache.add 성공 시 True 반환
        - 락 키가 캐시에 존재
        """
        result: bool = self.trainer._acquire_lock_with_retry(ALS_TRAINING_LOCK_KEY, timeout=10)

        self.assertTrue(result)
        self.assertIsNotNone(cache.get(ALS_TRAINING_LOCK_KEY))

    def test_acquire_lock_retries_with_exponential_backoff(self) -> None:
        """Exponential backoff 재시도
        - 락 획득 실패 시 재시도
        - 백오프 시간: 1초 → 2초 → 4초 → 8초 → 16초
        - 최대 재시도 횟수: MAX_CACHE_LOAD_RETRIES
        """
        # 락이 이미 잡혀있는 상태
        cache.set(ALS_TRAINING_LOCK_KEY, "locked", timeout=10)

        with patch("time.sleep") as mock_sleep:
            # 락이 계속 잡혀있도록 설정
            with patch.object(cache, "add", return_value=False):
                result: bool = self.trainer._acquire_lock_with_retry(ALS_TRAINING_LOCK_KEY, timeout=10)

            # 재시도 횟수 확인 (첫 시도 제외)
            self.assertEqual(mock_sleep.call_count, MAX_CACHE_LOAD_RETRIES - 1)

            self.assertFalse(result)


class ModelTrainerFullTrainingTests(IsolatedRedisTestClient):
    """ModelTrainer Full Training 테스트"""

    def setUp(self) -> None:
        super().setUp()
        self.temp_dir: "tempfile.TemporaryDirectory[str]" = tempfile.TemporaryDirectory()
        self.data_loader: DataLoader = DataLoader()
        self.trainer: ModelTrainer = ModelTrainer(self.data_loader)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()
        super().tearDown()

    def test_train_and_save_full_model_returns_false_when_no_data(self) -> None:
        """데이터 없을 때 학습 스킵 검증
        - build_user_item_matrix가 None 반환
        - False 반환
        """
        with patch.object(self.data_loader, "build_user_item_matrix", return_value=None):
            result: bool = self.trainer.train_and_save_full_model()

        self.assertFalse(result)

    def test_train_and_save_full_model_transposes_matrix(self) -> None:
        """행렬 전치 확인 검증
        - implicit ALS는 item-user 행렬 기대
        - user-item 행렬을 전치하여 전달
        """
        test_matrix: csr_matrix = csr_matrix(np.array([[1.0, 2.0]], dtype=np.float32))  # 1x2
        matrix_bundle: Tuple[csr_matrix, Dict[int, int], Dict[int, int], List[int], List[int], bool] = (
            test_matrix,
            {1: 0},
            {10: 0, 20: 1},
            [1],
            [10, 20],
            False,
        )

        # 실제 ALS 모델 인스턴스 생성
        mock_model = AlternatingLeastSquares(factors=10, iterations=1)

        with patch.object(self.data_loader, "build_user_item_matrix", return_value=matrix_bundle):
            # 인스턴스 메서드 패칭
            with patch.object(mock_model, "fit") as mock_fit:
                with patch(
                    "apps.lecture.services.recommendation_service.model_trainer.AlternatingLeastSquares",
                    return_value=mock_model,
                ):
                    with patch.object(self.trainer, "_safe_dump_model", return_value=True):
                        result: bool = self.trainer.train_and_save_full_model()

        # 검증: fit 호출 시 전치된 행렬 전달
        self.assertTrue(result)
        mock_fit.assert_called_once()

        # fit에 전달된 행렬 확인
        fitted_matrix = mock_fit.call_args[0][0]
        self.assertEqual(fitted_matrix.shape, (2, 1))  # 전치됨 (원본 1x2 -> 2x1)


class ModelTrainerPartialTrainingTests(IsolatedRedisTestClient):
    """ModelTrainer Partial Training 테스트"""

    def setUp(self) -> None:
        super().setUp()
        self.temp_dir: "tempfile.TemporaryDirectory[str]" = tempfile.TemporaryDirectory()
        self.data_loader: DataLoader = DataLoader()
        self.trainer: ModelTrainer = ModelTrainer(self.data_loader)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()
        super().tearDown()

    def test_partial_fit_falls_back_when_no_existing_model(self) -> None:
        """기존 모델 없을 때 Full Training 폴백 테스트
        - load_model_and_mappings가 None 반환
        - train_and_save_full_model 호출
        """
        with patch.object(
            self.trainer,
            "load_model_and_mappings",
            return_value=(None, None, None, None, None, None, None),
        ):
            with patch.object(self.trainer, "train_and_save_full_model", return_value=True) as mock_full:
                result: bool = self.trainer.partial_fit_model_and_save()

        mock_full.assert_called_once()
        self.assertTrue(result)

    def test_partial_fit_detects_new_user(self) -> None:
        """신규 사용자 감지 시 Full Training 폴백 테스트
        - is_new_user_added=True
        - train_and_save_full_model 호출
        """
        existing_bundle = ModelBundleFactory.create_model_bundle()

        new_bundle = ModelBundleFactory.create_matrix_bundle(
            user_to_idx={1: 0, 2: 1},  # 사용자 2명으로 증가
            users=[1, 2],
            is_new_user_added=True,  # 신규 사용자 플래그
        )

        with patch.object(self.trainer, "load_model_and_mappings", return_value=existing_bundle):
            with patch.object(self.data_loader, "build_user_item_matrix", return_value=new_bundle):
                with patch.object(self.trainer, "train_and_save_full_model", return_value=True) as mock_full:
                    result: bool = self.trainer.partial_fit_model_and_save()

        mock_full.assert_called_once()
        self.assertTrue(result)

    def test_partial_fit_returns_true_when_no_new_data(self) -> None:
        """신규 데이터 없을 때 학습 스킵 테스트
        - build_user_item_matrix가 None 반환
        - True 반환 (성공으로 간주)
        """
        existing_bundle = ModelBundleFactory.create_model_bundle()

        with patch.object(self.trainer, "load_model_and_mappings", return_value=existing_bundle):
            with patch.object(self.data_loader, "build_user_item_matrix", return_value=None):
                result: bool = self.trainer.partial_fit_model_and_save()

        self.assertTrue(result)


class ModelTrainerPartialFitEdgeCasesTests(IsolatedRedisTestClient):
    """ModelTrainer Partial Fit 엣지 케이스 테스트"""

    def setUp(self) -> None:
        super().setUp()
        self.temp_dir: "tempfile.TemporaryDirectory[str]" = tempfile.TemporaryDirectory()
        self.data_loader: DataLoader = DataLoader()
        self.trainer: ModelTrainer = ModelTrainer(self.data_loader)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()
        super().tearDown()

    def test_partial_fit_user_shape_mismatch(self) -> None:
        """사용자 수 불일치 시 Full Training 폴백 테스트
        - 신규 사용자 플래그는 False지만 shape 다름
        - train_and_save_full_model 호출
        """
        existing_bundle = ModelBundleFactory.create_model_bundle(
            matrix=csr_matrix(np.array([[1.0]], dtype=np.float32)),  # 1x1
        )

        new_bundle = ModelBundleFactory.create_matrix_bundle(
            matrix=csr_matrix(np.array([[1.0], [2.0]], dtype=np.float32)),  # 2x1 (사용자 증가)
            user_to_idx={1: 0, 2: 1},
            users=[1, 2],
            is_new_user_added=False,  # 플래그는 False
        )

        with patch.object(self.trainer, "load_model_and_mappings", return_value=existing_bundle):
            with patch.object(self.data_loader, "build_user_item_matrix", return_value=new_bundle):
                with patch.object(self.trainer, "train_and_save_full_model", return_value=True) as mock_full:
                    result: bool = self.trainer.partial_fit_model_and_save()

        mock_full.assert_called_once()
        self.assertTrue(result)

    def test_partial_fit_old_lectures_none(self) -> None:
        """old_lectures가 None일 때 Full Training 폴백 테스트
        - 강의 수 불일치 + old_lectures=None
        - train_and_save_full_model 호출
        """
        existing_bundle = ModelBundleFactory.create_model_bundle(
            matrix=csr_matrix(np.array([[1.0]], dtype=np.float32)),  # 1x1
            lectures=None,  # old_lectures가 None
        )

        new_bundle = ModelBundleFactory.create_matrix_bundle(
            matrix=csr_matrix(np.array([[1.0, 2.0]], dtype=np.float32)),  # 1x2 (강의 증가)
            lecture_to_idx={10: 0, 20: 1},
            lectures=[10, 20],
            is_new_user_added=False,
        )

        with patch.object(self.trainer, "load_model_and_mappings", return_value=existing_bundle):
            with patch.object(self.data_loader, "build_user_item_matrix", return_value=new_bundle):
                with patch.object(self.trainer, "train_and_save_full_model", return_value=True) as mock_full:
                    result: bool = self.trainer.partial_fit_model_and_save()

        mock_full.assert_called_once()
        self.assertTrue(result)

    def test_partial_fit_new_lecture_detected(self) -> None:
        """신규 강의 감지 시 Full Training 폴백 테스트
        - 기존에 없던 강의 ID 추가
        - train_and_save_full_model 호출
        """
        existing_bundle = ModelBundleFactory.create_model_bundle(
            matrix=csr_matrix(np.array([[1.0]], dtype=np.float32)),  # 1x1
            lectures=[10],  # 강의 1개
        )

        new_bundle = ModelBundleFactory.create_matrix_bundle(
            matrix=csr_matrix(np.array([[1.0, 2.0]], dtype=np.float32)),  # 1x2
            lecture_to_idx={10: 0, 20: 1},  # 강의 20 추가
            lectures=[10, 20],
            is_new_user_added=False,
        )

        with patch.object(self.trainer, "load_model_and_mappings", return_value=existing_bundle):
            with patch.object(self.data_loader, "build_user_item_matrix", return_value=new_bundle):
                with patch.object(self.trainer, "train_and_save_full_model", return_value=True) as mock_full:
                    result: bool = self.trainer.partial_fit_model_and_save()

        mock_full.assert_called_once()
        self.assertTrue(result)

    def test_partial_fit_matrix_expansion(self) -> None:
        """행렬 확장 테스트 (기존 강의 중 일부만 상호작용)
        - 기존 행렬: 1x2 (사용자 1명, 강의 2개)
        - 신규 행렬: 1x1 (사용자 1명, 강의 1개만 상호작용)
        - 신규 강의 없음 (기존 강의 중 일부만 활동)
        - 행렬 확장 후 partial_fit 실행
        """
        mock_model: MagicMock = MagicMock(spec=AlternatingLeastSquares)
        mock_model.partial_fit_users = MagicMock()
        mock_model.partial_fit_items = MagicMock()

        # 기존 행렬: 1x2
        old_matrix: csr_matrix = csr_matrix(np.array([[1.0, 2.0]], dtype=np.float32))
        existing_bundle = ModelBundleFactory.create_model_bundle(
            model=mock_model,
            user_to_idx={1: 0},
            lecture_to_idx={10: 0, 20: 1},  # 강의 2개
            users=[1],
            lectures=[10, 20],
            matrix=old_matrix,
        )

        # 신규 행렬: 1x1 (강의 10만 상호작용)
        new_matrix: csr_matrix = csr_matrix(np.array([[3.0]], dtype=np.float32))
        new_bundle = ModelBundleFactory.create_matrix_bundle(
            matrix=new_matrix,
            user_to_idx={1: 0},
            lecture_to_idx={10: 0},  # 강의 1개만
            users=[1],
            lectures=[10, 20],  # 전체 강의 목록은 동일
            is_new_user_added=False,
        )

        with patch.object(self.trainer, "load_model_and_mappings", return_value=existing_bundle):
            with patch.object(self.data_loader, "build_user_item_matrix", return_value=new_bundle):
                with patch.object(self.trainer, "_safe_dump_model", return_value=True):
                    result: bool = self.trainer.partial_fit_model_and_save()

        # 검증
        self.assertTrue(result)
        mock_model.partial_fit_users.assert_called_once()
        mock_model.partial_fit_items.assert_called_once()

    def test_partial_fit_implicit_error(self) -> None:
        """implicit partial_fit 에러 시 Full Training 폴백 테스트
        - partial_fit_users 실행 중 예외 발생
        - train_and_save_full_model 호출
        """
        mock_model: MagicMock = MagicMock(spec=AlternatingLeastSquares)
        mock_model.partial_fit_users = MagicMock(side_effect=Exception("Implicit error"))

        old_matrix: csr_matrix = csr_matrix(np.array([[1.0]], dtype=np.float32))
        existing_bundle = ModelBundleFactory.create_model_bundle(
            model=mock_model,
            matrix=old_matrix,
        )

        new_matrix: csr_matrix = csr_matrix(np.array([[2.0]], dtype=np.float32))
        new_bundle = ModelBundleFactory.create_matrix_bundle(
            matrix=new_matrix,
            is_new_user_added=False,
        )

        with patch.object(self.trainer, "load_model_and_mappings", return_value=existing_bundle):
            with patch.object(self.data_loader, "build_user_item_matrix", return_value=new_bundle):
                with patch.object(self.trainer, "train_and_save_full_model", return_value=True) as mock_full:
                    result: bool = self.trainer.partial_fit_model_and_save()

        mock_full.assert_called_once()
        self.assertTrue(result)

    def test_partial_fit_lock_acquisition_failure(self) -> None:
        """락 획득 실패 시 False 반환 테스트
        - _acquire_lock_with_retry가 False 반환
        - partial_fit 실행 안됨
        """
        mock_model: MagicMock = MagicMock(spec=AlternatingLeastSquares)
        mock_model.partial_fit_users = MagicMock()
        mock_model.partial_fit_items = MagicMock()

        old_matrix: csr_matrix = csr_matrix(np.array([[1.0]], dtype=np.float32))
        existing_bundle = ModelBundleFactory.create_model_bundle(
            model=mock_model,
            matrix=old_matrix,
        )

        new_matrix: csr_matrix = csr_matrix(np.array([[2.0]], dtype=np.float32))
        new_bundle = ModelBundleFactory.create_matrix_bundle(
            matrix=new_matrix,
            is_new_user_added=False,
        )

        with patch.object(self.trainer, "load_model_and_mappings", return_value=existing_bundle):
            with patch.object(self.data_loader, "build_user_item_matrix", return_value=new_bundle):
                with patch.object(self.trainer, "_acquire_lock_with_retry", return_value=False):
                    result: bool = self.trainer.partial_fit_model_and_save()

        self.assertFalse(result)

    def test_partial_fit_cache_invalidation(self) -> None:
        """Partial fit 성공 시 캐시 무효화 테스트
        - _safe_dump_model 성공
        - 모든 ALS 캐시 키 삭제
        """
        mock_model: MagicMock = MagicMock(spec=AlternatingLeastSquares)
        mock_model.partial_fit_users = MagicMock()
        mock_model.partial_fit_items = MagicMock()

        old_matrix: csr_matrix = csr_matrix(np.array([[1.0]], dtype=np.float32))
        existing_bundle = ModelBundleFactory.create_model_bundle(
            model=mock_model,
            matrix=old_matrix,
        )

        new_matrix: csr_matrix = csr_matrix(np.array([[2.0]], dtype=np.float32))
        new_bundle = ModelBundleFactory.create_matrix_bundle(
            matrix=new_matrix,
            is_new_user_added=False,
        )

        with patch.object(self.trainer, "load_model_and_mappings", return_value=existing_bundle):
            with patch.object(self.data_loader, "build_user_item_matrix", return_value=new_bundle):
                with patch.object(self.trainer, "_safe_dump_model", return_value=True):
                    with patch.object(cache, "delete"):
                        result: bool = self.trainer.partial_fit_model_and_save()

        # 검증
        self.assertTrue(result)
        mock_model.partial_fit_users.assert_called_once()
        mock_model.partial_fit_items.assert_called_once()
