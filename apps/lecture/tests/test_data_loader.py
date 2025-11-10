import os

os.environ["TQDM_DISABLE"] = "1"

import sys
from unittest.mock import MagicMock

sys.modules["tqdm"] = MagicMock()
sys.modules["tqdm.auto"] = MagicMock()
import logging
import warnings
from datetime import timedelta

import numpy as np
from django.core.cache import cache
from django.utils import timezone
from scipy.sparse import coo_matrix, csr_matrix

from apps.core.utils.isolated_cache_testcase import IsolatedRedisTestClient
from apps.lecture.models import (
    LectureBookmark,
    LectureSearchLog,
    UserPreferCategory,
)
from apps.lecture.services.recommendation_service.constants import (
    HALF_LIFE_DAYS,
    LECTURE_CATEGORY_MAP_CACHE_KEY,
    USER_INTERACTION_WEIGHTS,
)
from apps.lecture.services.recommendation_service.data_loader import (
    DataLoader,
    _normalize_sparse_rows_l1,
)
from apps.lecture.tests.base_lecture import BaseLectureTest
from apps.studies.models.groups import GroupMember, StudyGroup, StudyLecture
from apps.users.models import User


# ========================================
# Base Test Class
# ========================================
class DataLoaderTestBase(IsolatedRedisTestClient, BaseLectureTest):
    """DataLoader 테스트 Base 클래스 (Redis 캐시 격리 + 강의 픽스처)"""

    data_loader: DataLoader
    user1: User
    user2: User

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        logging.getLogger("apps.lecture.services.recommendation_service.model_trainer").setLevel(logging.CRITICAL + 1)
        logging.getLogger("apps.lecture.services.recommendation_service.recommender").setLevel(logging.CRITICAL + 1)
        logging.getLogger("apps.lecture.services.recommendation_service.data_loader").setLevel(logging.CRITICAL + 1)
        logging.getLogger("apps.lecture.tasks").setLevel(logging.CRITICAL + 1)

        # 외부 라이브러리 경고 억제
        warnings.filterwarnings("ignore", category=RuntimeWarning, module="implicit")
        warnings.filterwarnings("ignore", module="implicit.utils")

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()

        # DataLoader 인스턴스 생성
        cls.data_loader = DataLoader()

        # 추가 테스트 사용자 생성
        cls.user1 = User.objects.create(
            email="test1@example.com",
            name="Test User 1",
            nickname="testuser1",
            phone_number="010-1234-5678",
            gender="MALE",
            birthday="1990-01-01",
        )
        cls.user2 = User.objects.create(
            email="test2@example.com",
            name="Test User 2",
            nickname="testuser2",
            phone_number="010-1234-5679",
            gender="FEMALE",
            birthday="1995-05-15",
        )

        # 사용자 선호 카테고리 설정
        UserPreferCategory.objects.create(user=cls.user1, category=cls.category1)


# ========================================
# 1. L1 정규화 테스트
# ========================================
class NormalizeSparseRowsTestCase(DataLoaderTestBase):
    """_normalize_sparse_rows_l1() 테스트"""

    def test_normalize_sparse_rows_l1_csr(self) -> None:
        """CSR 형식 L1 정규화 테스트"""
        # Given: 테스트 행렬
        matrix = csr_matrix(np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32))

        # When: L1 정규화
        normalized = _normalize_sparse_rows_l1(matrix, return_format="csr")

        # Then: 각 행의 합이 1.0
        row_sums = normalized.sum(axis=1).A1
        np.testing.assert_array_almost_equal(row_sums, [1.0, 1.0])

    def test_normalize_sparse_rows_l1_coo(self) -> None:
        """COO 형식 L1 정규화 테스트"""
        # Given: 테스트 행렬
        matrix = coo_matrix(np.array([[2.0, 2.0], [5.0, 5.0]], dtype=np.float32))

        # When: L1 정규화
        normalized = _normalize_sparse_rows_l1(matrix, return_format="coo")

        # Then: COO 형식 반환 및 정규화 확인
        self.assertEqual(type(normalized).__name__, "coo_matrix")


# ========================================
# 2. 시간 감쇠 계산 테스트
# ========================================
class DecayFactorTestCase(DataLoaderTestBase):
    """_get_decay_factor() 및 _get_decay_factor_array() 테스트"""

    def test_get_decay_factor_no_decay(self) -> None:
        """0일 경과 시 감쇠 없음 테스트"""
        # Given: 현재 시간
        reference_time = timezone.now()
        event_time = reference_time

        # When: 감쇠 계산
        decay = self.data_loader._get_decay_factor(event_time, reference_time)

        # Then: 감쇠 없음 (1.0)
        self.assertAlmostEqual(decay, 1.0, places=5)

    def test_get_decay_factor_half_life(self) -> None:
        """반감기(7일) 경과 시 0.5 감쇠 테스트"""
        # Given: 7일 전 이벤트
        reference_time = timezone.now()
        event_time = reference_time - timedelta(days=HALF_LIFE_DAYS)

        # When: 감쇠 계산
        decay = self.data_loader._get_decay_factor(event_time, reference_time)

        # Then: 0.5 감쇠
        self.assertAlmostEqual(decay, 0.5, places=5)

    def test_get_decay_factor_two_half_lives(self) -> None:
        """반감기 2배(14일) 경과 시 0.25 감쇠 테스트"""
        # Given: 14일 전 이벤트
        reference_time = timezone.now()
        event_time = reference_time - timedelta(days=HALF_LIFE_DAYS * 2)

        # When: 감쇠 계산
        decay = self.data_loader._get_decay_factor(event_time, reference_time)

        # Then: 0.25 감쇠
        self.assertAlmostEqual(decay, 0.25, places=5)

    def test_get_decay_factor_array_vectorized(self) -> None:
        """벡터화된 감쇠 계산 테스트"""
        # Given: 여러 경과 일수
        days_since = np.array([0, HALF_LIFE_DAYS, HALF_LIFE_DAYS * 2], dtype=np.float32)

        # When: 벡터화된 감쇠 계산
        decays = self.data_loader._get_decay_factor_array(days_since)

        # Then: 각각 1.0, 0.5, 0.25
        expected = np.array([1.0, 0.5, 0.25], dtype=np.float32)
        np.testing.assert_array_almost_equal(decays, expected, decimal=5)


# ========================================
# 3. 강의 카테고리 맵 로드 테스트
# ========================================
class GetLectureCategoryMapTestCase(DataLoaderTestBase):
    """get_lecture_category_map() 테스트"""

    def test_get_lecture_category_map_from_db(self) -> None:
        """DB에서 강의 카테고리 맵 로드 테스트"""
        # Given: 캐시 비어있음
        cache.delete(LECTURE_CATEGORY_MAP_CACHE_KEY)

        # When: 카테고리 맵 로드
        result = self.data_loader.get_lecture_category_map()

        # Then: lecture1 -> category1 매핑 확인
        self.assertIn(self.lecture1.id, result)
        self.assertIn(self.category1.id, result[self.lecture1.id])

    def test_get_lecture_category_map_cache_hit(self) -> None:
        """캐시 히트 테스트"""
        # Given: 캐시에 데이터 설정
        cached_data = {self.lecture1.id: {self.category1.id}}
        cache.set(LECTURE_CATEGORY_MAP_CACHE_KEY, cached_data)

        # When: 카테고리 맵 로드
        result = self.data_loader.get_lecture_category_map()

        # Then: 캐시된 데이터 반환
        self.assertEqual(result, cached_data)

    def test_get_lecture_category_map_cache_miss_then_hit(self) -> None:
        """캐시 미스 후 히트 테스트"""
        # Given: 캐시 비어있음
        cache.delete(LECTURE_CATEGORY_MAP_CACHE_KEY)

        # When: 첫 번째 로드 (DB에서)
        result1 = self.data_loader.get_lecture_category_map()

        # When: 두 번째 로드 (캐시에서)
        result2 = self.data_loader.get_lecture_category_map()

        # Then: 동일한 결과
        self.assertEqual(result1, result2)


# ========================================
# 4. 사용자 상호작용 로드 테스트
# ========================================
class LoadUserInteractionsTestCase(DataLoaderTestBase):
    """_load_user_interactions() 테스트"""

    def test_load_user_interactions_bookmarks(self) -> None:
        """북마크 상호작용 로드 테스트"""
        # Given: 북마크 생성
        LectureBookmark.objects.create(user=self.user1, lecture=self.lecture1)

        # When: 상호작용 로드
        result = self.data_loader._load_user_interactions(last_trained_at=None, reference_time=timezone.now())

        # Then: 북마크 가중치 적용
        key = (self.user1.id, self.lecture1.id)
        self.assertIn(key, result)
        self.assertEqual(result[key], USER_INTERACTION_WEIGHTS["bookmark"])

    def test_load_user_interactions_study_with_decay(self) -> None:
        """스터디 상호작용 로드 및 시간 감쇠 테스트"""
        # Given: 스터디 그룹 및 멤버 생성
        study_group = StudyGroup.objects.create(
            name="Test Study",
            introduction="Test",
            max_headcount=10,
            start_at=timezone.now(),
            end_at=timezone.now() + timedelta(days=30),
            status="ONGOING",
        )

        # 멤버를 먼저 생성 (8일 전)
        member = GroupMember.objects.create(study_group=study_group, user=self.user1, is_leader=True)
        GroupMember.objects.filter(pk=member.pk).update(created_at=timezone.now() - timedelta(days=8))

        # 7일 전 강의 추가
        study_lecture = StudyLecture.objects.create(study_group=study_group, lecture=self.lecture1)
        StudyLecture.objects.filter(pk=study_lecture.pk).update(created_at=timezone.now() - timedelta(days=7))

        # When: 상호작용 로드
        reference_time = timezone.now()
        result = self.data_loader._load_user_interactions(last_trained_at=None, reference_time=reference_time)

        # Then: 시간 감쇠 적용된 가중치
        key = (self.user1.id, self.lecture1.id)
        self.assertIn(key, result)
        expected = USER_INTERACTION_WEIGHTS["study_participation"] * 0.5
        self.assertAlmostEqual(result[key], expected, places=2)

    def test_load_user_interactions_partial_fit_filtering(self) -> None:
        """Partial Fit 필터링 테스트"""
        # Given: 과거 북마크 생성
        past_date = timezone.now() - timedelta(days=10)
        bookmark = LectureBookmark.objects.create(user=self.user1, lecture=self.lecture1)
        bookmark.created_at = past_date
        bookmark.save()

        # When: Partial Fit 모드로 로드 (최근 5일만)
        cutoff_time = timezone.now() - timedelta(days=5)
        result = self.data_loader._load_user_interactions(last_trained_at=cutoff_time, reference_time=timezone.now())

        # Then: 과거 북마크는 제외됨
        key = (self.user1.id, self.lecture1.id)
        self.assertNotIn(key, result)

    def test_load_user_interactions_multiple_sources(self) -> None:
        """여러 소스의 상호작용 통합 테스트"""
        # Given: 북마크 + 스터디 동시 존재
        LectureBookmark.objects.create(user=self.user1, lecture=self.lecture1)

        study_group = StudyGroup.objects.create(
            name="Test Study",
            introduction="Test",
            max_headcount=10,
            start_at=timezone.now(),
            end_at=timezone.now() + timedelta(days=30),
            status="ONGOING",
        )
        member = GroupMember.objects.create(study_group=study_group, user=self.user1, is_leader=True)
        GroupMember.objects.filter(pk=member.pk).update(created_at=timezone.now() - timedelta(days=8))
        study_lecture = StudyLecture.objects.create(study_group=study_group, lecture=self.lecture1)
        StudyLecture.objects.filter(pk=study_lecture.pk).update(created_at=timezone.now() - timedelta(days=7))

        # When: 상호작용 로드
        result = self.data_loader._load_user_interactions(last_trained_at=None, reference_time=timezone.now())

        # Then: 두 가중치가 합산됨
        key = (self.user1.id, self.lecture1.id)
        expected = USER_INTERACTION_WEIGHTS["bookmark"] + USER_INTERACTION_WEIGHTS["study_participation"] * 0.5
        self.assertAlmostEqual(result[key], expected, places=2)


# ========================================
# 5. 아이템 피처 로드 테스트
# ========================================
class LoadItemFeaturesTestCase(DataLoaderTestBase):
    """_load_item_features() 테스트"""

    def test_load_item_features_category_matching(self) -> None:
        """카테고리 매칭 피처 테스트"""
        # Given: 사용자 선호 카테고리와 강의 카테고리 일치
        all_interactions = {(self.user1.id, self.lecture1.id): 1.0}

        # When: 아이템 피처 로드 (올바른 인자명 사용)
        result = self.data_loader._load_item_features(
            all_interactions=all_interactions,
            last_trained_at=None,
        )

        # Then: 카테고리 매칭 가중치 적용
        key = (self.user1.id, self.lecture1.id)
        self.assertIn(key, result)


# ========================================
# 6. 검색 상호작용 로드 테스트
# ========================================
class LoadSearchInteractionsTestCase(DataLoaderTestBase):
    """_load_search_interactions() 테스트"""

    def test_load_search_interactions_basic(self) -> None:
        """검색 상호작용 기본 로드 테스트"""
        # Given: 검색 로그 생성
        LectureSearchLog.objects.create(user=self.user1, keyword=self.lecture1.title)

        # When: 검색 상호작용 로드
        reference_time = timezone.now()
        result = self.data_loader._load_search_interactions(last_trained_at=None, reference_time=reference_time)

        # Then: 검색 가중치 적용
        key = (self.user1.id, self.lecture1.id)
        self.assertIn(key, result)


# ========================================
# 7. 전체 행렬 구축 테스트
# ========================================
class BuildUserItemMatrixTestCase(DataLoaderTestBase):
    """build_user_item_matrix() 테스트"""

    def test_build_user_item_matrix_full_training(self) -> None:
        """Full Training 모드 테스트"""
        # Given: 북마크 생성
        LectureBookmark.objects.create(user=self.user1, lecture=self.lecture1)

        # When: 전체 행렬 구축
        result = self.data_loader.build_user_item_matrix()

        # Then: None 체크 후 언패킹
        assert result is not None, "Matrix should be built"
        matrix, u_to_idx, l_to_idx, users, lectures, is_new_user = result

        # 행렬 생성 확인
        self.assertEqual(matrix.shape[0], 1)  # 1명의 사용자
        self.assertEqual(matrix.shape[1], 2)  # 2개의 강의
        self.assertFalse(is_new_user)

    def test_build_user_item_matrix_normalization(self) -> None:
        """행렬 정규화 테스트"""
        # Given: 북마크 생성
        LectureBookmark.objects.create(user=self.user1, lecture=self.lecture1)

        # When: 정규화된 행렬 구축
        result = self.data_loader.build_user_item_matrix(normalize_rows=True)

        # Then: None 체크 후 언패킹
        assert result is not None, "Matrix should be built"
        matrix, _, _, _, _, _ = result

        # 행 합이 1.0
        row_sums = matrix.sum(axis=1)
        self.assertAlmostEqual(float(row_sums[0]), 1.0, places=5)

    def test_build_user_item_matrix_csr_format(self) -> None:
        """CSR 형식 반환 테스트"""
        # Given: 북마크 생성
        LectureBookmark.objects.create(user=self.user1, lecture=self.lecture1)

        # When: CSR 형식 요청
        result = self.data_loader.build_user_item_matrix(return_format="csr")

        # Then: None 체크 후 언패킹
        assert result is not None, "Matrix should be built"
        matrix, _, _, _, _, _ = result

        # CSR 형식 확인
        self.assertEqual(type(matrix).__name__, "csr_matrix")

    def test_build_user_item_matrix_coo_format(self) -> None:
        """COO 형식 반환 테스트"""
        # Given: 북마크 생성
        LectureBookmark.objects.create(user=self.user1, lecture=self.lecture1)

        # When: COO 형식 요청
        result = self.data_loader.build_user_item_matrix(return_format="coo")

        # Then: None 체크 후 언패킹
        assert result is not None, "Matrix should be built"
        matrix, _, _, _, _, _ = result

        # COO 형식 확인
        self.assertEqual(type(matrix).__name__, "coo_matrix")

    def test_build_user_item_matrix_empty_data(self) -> None:
        """데이터 없을 때 테스트"""
        # Given: 상호작용 없음

        # When: 행렬 구축
        result = self.data_loader.build_user_item_matrix()

        # Then: None 반환 또는 빈 행렬
        if result is not None:
            matrix, _, _, _, _, _ = result
            self.assertEqual(matrix.shape[0], 0)

    def test_build_user_item_matrix_single_interaction(self) -> None:
        """단일 상호작용 테스트"""
        # Given: 하나의 북마크만
        LectureBookmark.objects.create(user=self.user1, lecture=self.lecture1)

        # When: 행렬 구축
        result = self.data_loader.build_user_item_matrix()

        # Then: 1x2 행렬 생성
        assert result is not None
        matrix, _, _, _, _, _ = result
        self.assertEqual(matrix.shape, (1, 2))

    def test_build_user_item_matrix_cold_start(self) -> None:
        """사용자는 존재하지만 상호작용 없을 때 테스트"""
        # Given: 사용자만 존재, 상호작용 없음

        # When: 행렬 구축 (기존 사용자 지정)
        result = self.data_loader.build_user_item_matrix(existing_users=[self.user1.id])

        # Then: 빈 행렬 생성
        if result is not None:
            matrix, _, _, _, _, _ = result
            self.assertEqual(matrix.shape[0], 0)

    def test_build_user_item_matrix_partial_fit_no_new_data(self) -> None:
        """Partial Fit 모드에서 신규 데이터 없을 때 테스트"""
        # Given: 과거 북마크만 존재
        past_date = timezone.now() - timedelta(days=10)
        bookmark = LectureBookmark.objects.create(user=self.user1, lecture=self.lecture1)
        bookmark.created_at = past_date
        bookmark.save()

        # When: Partial Fit 모드 (최근 5일만)
        cutoff_time = timezone.now() - timedelta(days=5)
        result = self.data_loader.build_user_item_matrix(existing_users=[self.user1.id], last_trained_at=cutoff_time)

        # Then: None 반환 (신규 데이터 없음)
        self.assertIsNone(result)
