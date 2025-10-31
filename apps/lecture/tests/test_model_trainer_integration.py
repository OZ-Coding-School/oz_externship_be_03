import os
import tempfile
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple
from unittest.mock import patch

import joblib  # type: ignore
import numpy as np
from django.test import override_settings
from django.utils import timezone
from implicit.als import AlternatingLeastSquares  # type: ignore
from scipy.sparse import csr_matrix

from apps.core.utils.isolated_cache_testcase import IsolatedRedisTestClient
from apps.lecture.services.recommendation_service.data_loader import DataLoader
from apps.lecture.services.recommendation_service.model_trainer import (
    MODEL_BUNDLE_PATH,
    ModelTrainer,
)


class SimpleMockModel:
    """Pickle 가능한 간단한 Mock ALS 모델"""

    def __init__(self) -> None:
        self.factors = 50  # 잠재 요인 개수
        self.iterations = 15  # 반복 횟수

    def fit(self, matrix: csr_matrix) -> None:
        """Mock fit 메서드"""
        pass


class ModelTrainerIntegrationTests(IsolatedRedisTestClient):
    """ModelTrainer 통합 테스트 - 실제 파일 시스템과 Redis 사용"""

    def setUp(self) -> None:
        super().setUp()
        # 임시 디렉토리 생성 (테스트 후 자동 삭제)
        self.temp_dir: "tempfile.TemporaryDirectory[str]" = tempfile.TemporaryDirectory()

        # Django 설정 임시 변경 (모델 저장 경로를 임시 디렉토리로)
        self.settings_override = override_settings(MODEL_STORAGE_PATH=self.temp_dir.name)
        self.settings_override.enable()

        # 테스트 대상 객체 생성
        self.data_loader: DataLoader = DataLoader()
        self.trainer: ModelTrainer = ModelTrainer(self.data_loader)

    def tearDown(self) -> None:
        self.settings_override.disable()  # 설정 원복
        self.temp_dir.cleanup()
        super().tearDown()

    def test_full_training_with_real_filesystem(self) -> None:
        """실제 파일 시스템에서 전체 학습 및 저장 테스트"""
        # 테스트용 희소 행렬 생성 (2x2)
        test_matrix: csr_matrix = csr_matrix(np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32))
        # 모델 학습에 필요한 데이터 번들
        matrix_bundle: Tuple[csr_matrix, Dict[int, int], Dict[int, int], List[int], List[int], bool] = (
            test_matrix,  # 사용자-강의 상호작용 행렬
            {1: 0, 2: 1},  # 사용자 ID -> 행렬 인덱스 매핑
            {10: 0, 20: 1},  # 강의 ID -> 행렬 인덱스 매핑
            [1, 2],  # 사용자 ID 리스트
            [10, 20],  # 강의 ID 리스트
            False,  # 신규 사용자 존재 여부
        )

        # Mock 객체로 실제 데이터 로딩/학습 대체
        with patch.object(self.data_loader, "build_user_item_matrix", return_value=matrix_bundle):
            with patch(
                "apps.lecture.services.recommendation_service.model_trainer.AlternatingLeastSquares"
            ) as mock_als:
                mock_als.return_value = SimpleMockModel()  # 가짜 모델 반환

                # 실제 테스트 실행
                result: bool = self.trainer.train_and_save_full_model()

        # 검증
        self.assertTrue(result)  # 학습 성공 확인
        self.assertTrue(os.path.exists(MODEL_BUNDLE_PATH))  # 파일 저장 확인

    def test_model_load_and_save_cycle(self) -> None:
        """파일에 모델 저장 후 로드하여 원본 데이터 일치 검증"""
        # 저장할 테스트 객체 (모델 + 메타데이터)
        test_obj: Dict[str, Any] = {
            "model": SimpleMockModel(),  # 학습된 모델
            "user_to_idx": {1: 0, 2: 1, 3: 2},  # 사용자 매핑
            "lecture_to_idx": {10: 0, 20: 1, 30: 2},  # 강의 매핑
            "users": [1, 2, 3],
            "lectures": [10, 20, 30],
            "matrix": csr_matrix(  # 3x3 상호작용 행렬
                np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]], dtype=np.float32)
            ),
            "last_trained_at": timezone.now(),  # 학습 시각
        }

        # 저장 실행
        result: bool = self.trainer._safe_dump_model(test_obj)
        self.assertTrue(result)

        # 로드 실행
        loaded_bundle = self.trainer.load_model_and_mappings()
        self.assertIsNotNone(loaded_bundle)

        # 로드된 데이터 검증
        if loaded_bundle is not None:
            model, u_to_idx, l_to_idx, users, lectures, matrix, last_trained_at = loaded_bundle

            # 각 필드가 원본과 일치하는지 확인
            self.assertEqual(u_to_idx, {1: 0, 2: 1, 3: 2})
            self.assertEqual(l_to_idx, {10: 0, 20: 1, 30: 2})
            self.assertEqual(users, [1, 2, 3])
            self.assertEqual(lectures, [10, 20, 30])

            # 행렬 크기 확인
            self.assertIsNotNone(matrix)
            if matrix is not None:
                self.assertEqual(matrix.shape, (3, 3))

            # 학습 시각 존재 확인
            self.assertIsNotNone(last_trained_at)

    def test_partial_fit_with_new_users(self) -> None:
        """Partial Fit 시 신규 사용자 감지 및 Full Training 폴백

        시나리오:
        1. 기존 모델: 사용자 1명, 강의 1개
        2. 신규 데이터: 사용자 2명, 강의 2개 (신규 사용자 추가됨)
        3. 결과: 전체 재학습 실행
        """
        # 기존 모델 상태
        existing_model: SimpleMockModel = SimpleMockModel()
        old_matrix: csr_matrix = csr_matrix(np.array([[1.0]], dtype=np.float32))

        existing_bundle: Tuple[
            SimpleMockModel,
            Dict[int, int],
            Dict[int, int],
            List[int],
            List[int],
            csr_matrix,
            datetime,
        ] = (
            existing_model,
            {1: 0},  # 기존 사용자 1명
            {10: 0},  # 기존 강의 1개
            [1],
            [10],
            old_matrix,
            timezone.now() - timedelta(days=1),  # 기존 강의 1개
        )

        # 신규 데이터 (사용자 2명으로 증가)
        new_matrix: csr_matrix = csr_matrix(np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32))
        new_bundle: Tuple[csr_matrix, Dict[int, int], Dict[int, int], List[int], List[int], bool] = (
            new_matrix,
            {1: 0, 2: 1},  # 사용자 2명
            {10: 0, 20: 1},  # 강의 2개
            [1, 2],
            [10, 20],
            True,  # 신규 사용자 존재 플래그
        )

        with patch.object(self.trainer, "load_model_and_mappings", return_value=existing_bundle):
            with patch.object(self.data_loader, "build_user_item_matrix", return_value=new_bundle):
                with patch.object(self.trainer, "train_and_save_full_model", return_value=True) as mock_full:
                    # 부분 학습 시도
                    result: bool = self.trainer.partial_fit_model_and_save()

        # 검증: 전체 학습이 호출되었는지 확인
        mock_full.assert_called_once()
        self.assertTrue(result)

    def test_atomic_save_with_recovery(self) -> None:
        """저장 실패 시 백업에서 복구 검증

        시나리오:
        1. 초기 모델 저장 (사용자 1명)
        2. 새 모델 저장 시도 (사용자 2명) -> 실패 시뮬레이션
        3. 결과: 초기 모델(사용자 1명)이 유지됨
        """

        initial_obj: Dict[str, Any] = {
            "model": SimpleMockModel(),
            "user_to_idx": {1: 0},
            "lecture_to_idx": {10: 0},
            "users": [1],  # 사용자 1명
            "lectures": [10],
            "matrix": csr_matrix(np.array([[1.0]], dtype=np.float32)),
            "last_trained_at": timezone.now(),
        }

        result1: bool = self.trainer._safe_dump_model(initial_obj)
        self.assertTrue(result1)  # 초기 저장 성공

        # 저장 실패 시뮬레이션
        with patch("joblib.dump", side_effect=Exception("Simulated save error")):
            new_obj: Dict[str, Any] = {
                "model": SimpleMockModel(),
                "user_to_idx": {1: 0, 2: 1},
                "lecture_to_idx": {10: 0, 20: 1},
                "users": [1, 2],  # 사용자 2명으로 증가
                "lectures": [10, 20],
                "matrix": csr_matrix(np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)),
                "last_trained_at": timezone.now(),
            }

            # 저장 시도 (실패 예상)
            result: bool = self.trainer._safe_dump_model(new_obj)

        # 검증
        self.assertFalse(result)
        self.assertTrue(os.path.exists(MODEL_BUNDLE_PATH))  # 파일은 여전히 존재

        # 복구 확인: 초기 모델(사용자 1명)이 유지되었는지 검증
        loaded_data: Dict[str, Any] = joblib.load(MODEL_BUNDLE_PATH)
        self.assertEqual(len(loaded_data["users"]), 1)  # 사용자 1명 유지
