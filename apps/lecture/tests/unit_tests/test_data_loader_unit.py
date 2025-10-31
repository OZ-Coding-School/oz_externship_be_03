from datetime import datetime, timedelta
from typing import Any, Dict, List, Set, Tuple, Union

import numpy as np
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from scipy.sparse import coo_matrix, csr_matrix

from apps.core.utils.isolated_cache_testcase import IsolatedRedisTestClient
from apps.lecture.models import (
    CrawledLecture,
    LectureBookmark,
    LectureSearchLog,
)
from apps.lecture.services.recommendation_service.constants import (
    HALF_LIFE_DAYS,
    LECTURE_CATEGORY_MAP_CACHE_KEY,
)
from apps.lecture.services.recommendation_service.data_loader import (
    DataLoader,
    MatrixBundleExtended,
    _normalize_sparse_rows_l1,
)
from apps.lecture.tests.base_lecture import BaseLectureTest
from apps.studies.models.groups import (
    GroupMember,
    StudyGroup,
    StudyGroupStatus,
    StudyLecture,
)
from apps.users.models import User


class UserFactory:
    """사용자 생성 헬퍼"""

    @staticmethod
    def create_user(
        email: str = "test@example.com",
        nickname: str = "testuser",
        name: str = "Test User",
        phone_number: str = "010-1212-1212",
        gender: str = "MALE",
        birthday: str = "1990-01-01",
        password: str = "testpass123",
    ) -> User:
        """
        사용자 생성 헬퍼 메서드

        Args:
            email: 이메일 주소
            nickname: 닉네임
            name: 이름
            phone_number: 전화번호
            gender: 성별 ("MALE" 또는 "FEMALE")
            birthday: 생년월일 (YYYY-MM-DD)
            password: 비밀번호

        Returns:
            생성된 User 객체
        """
        return User.objects.create_user(
            email=email,
            password=password,
            nickname=nickname,
            name=name,
            phone_number=phone_number,
            gender=gender,
            birthday=birthday,
        )


class NormalizeSparseRowsL1Tests(TestCase):
    """
    _normalize_sparse_rows_l1 함수 테스트

    - 빈 행렬 처리
    - L1 정규화 (각 행의 합 = 1.0)
    - 0 행 처리
    - COO/CSR 포맷 반환
    """

    def test_empty_matrix_returns_empty(self) -> None:
        """빈 행렬 입력 시 빈 행렬 반환 테스트
        - shape (0, 0)
        - CSR 형식 반환
        """
        # 빈 데이터로 coo_matrix 생성
        data: np.ndarray = np.array([], dtype=np.float32)
        row: np.ndarray = np.array([], dtype=np.int32)
        col: np.ndarray = np.array([], dtype=np.int32)
        matrix: coo_matrix = coo_matrix((data, (row, col)), shape=(0, 0), dtype=np.float32)

        result: Union[coo_matrix, csr_matrix] = _normalize_sparse_rows_l1(matrix, return_format="csr")

        self.assertEqual(result.shape, (0, 0))
        self.assertIsInstance(result, csr_matrix)

    def test_l1_normalization_row_sums_equal_one(self) -> None:
        """L1 정규화 후 각 행의 합이 1.0인지 테스트
        - 2x2 행렬
        - 각 행의 합 = 1.0
        """
        # 2x2 행렬 생성
        data: np.ndarray = np.array([2.0, 3.0, 4.0, 1.0], dtype=np.float32)
        row: np.ndarray = np.array([0, 0, 1, 1], dtype=np.int32)
        col: np.ndarray = np.array([0, 1, 0, 1], dtype=np.int32)
        matrix: coo_matrix = coo_matrix((data, (row, col)), shape=(2, 2), dtype=np.float32)

        result: Union[coo_matrix, csr_matrix] = _normalize_sparse_rows_l1(matrix, return_format="csr")

        # 각 행의 합 계산
        row_sums: np.ndarray = np.array(result.sum(axis=1)).flatten()

        # 각 행의 합이 1.0인지 확인
        for row_sum in row_sums:
            self.assertAlmostEqual(row_sum, 1.0, places=5)

    def test_zero_row_remains_zero(self) -> None:
        """0 행은 정규화 후에도 0으로 유지 테스트
        - division by zero 방지
        """
        # 첫 번째 행은 0, 두 번째 행은 정상 값
        data: np.ndarray = np.array([0.0, 0.0, 2.0, 3.0], dtype=np.float32)
        row: np.ndarray = np.array([0, 0, 1, 1], dtype=np.int32)
        col: np.ndarray = np.array([0, 1, 0, 1], dtype=np.int32)
        matrix: coo_matrix = coo_matrix((data, (row, col)), shape=(2, 2), dtype=np.float32)

        result: Union[coo_matrix, csr_matrix] = _normalize_sparse_rows_l1(matrix, return_format="csr")

        # 첫 번째 행의 합은 0
        row_sums: np.ndarray = np.array(result.sum(axis=1)).flatten()
        self.assertAlmostEqual(row_sums[0], 0.0, places=5)
        # 두 번째 행의 합은 1.0
        self.assertAlmostEqual(row_sums[1], 1.0, places=5)

    def test_coo_format_return(self) -> None:
        """return_format='coo' 지정 시 COO 행렬 반환 테스트"""
        data: np.ndarray = np.array([2.0, 3.0], dtype=np.float32)
        row: np.ndarray = np.array([0, 0], dtype=np.int32)
        col: np.ndarray = np.array([0, 1], dtype=np.int32)
        matrix: coo_matrix = coo_matrix((data, (row, col)), shape=(1, 2), dtype=np.float32)

        result: Union[coo_matrix, csr_matrix] = _normalize_sparse_rows_l1(matrix, return_format="coo")

        self.assertIsInstance(result, coo_matrix)


class DataLoaderDecayFactorTests(TestCase):
    """
    DataLoader 시간 감쇠 함수 테스트

    - 단일 시간 감쇠 (_get_decay_factor)
    - 벡터화된 시간 감쇠 (_get_decay_factor_array)
    """

    def setUp(self) -> None:
        """각 테스트 전 초기화"""
        self.loader: DataLoader = DataLoader()

    def test_decay_factor_zero_days(self) -> None:
        """0일 경과 시 감쇠 계수 1.0 테스트
        - 최근 상호작용은 감쇠 없음
        """
        reference_time: datetime = timezone.now()
        created_at: datetime = reference_time

        decay: float = self.loader._get_decay_factor(created_at, reference_time)

        self.assertAlmostEqual(decay, 1.0, places=5)

    def test_decay_factor_half_life(self) -> None:
        """
        반감기(7일) 경과 시 감쇠 계수 0.5 검증
        - HALF_LIFE_DAYS = 7.0
        """
        reference_time: datetime = timezone.now()
        created_at: datetime = reference_time - timedelta(days=HALF_LIFE_DAYS)

        decay: float = self.loader._get_decay_factor(created_at, reference_time)

        self.assertAlmostEqual(decay, 0.5, places=5)

    def test_decay_factor_array_vectorized(self) -> None:
        """
        벡터화된 시간 감쇠 계산 검증
        - NumPy 배열 입력
        - 벡터화 연산으로 성능 향상
        """
        # 경과 일수 배열 (0일, 7일, 14일)
        days_since: np.ndarray = np.array([0.0, HALF_LIFE_DAYS, HALF_LIFE_DAYS * 2])

        decays: np.ndarray = self.loader._get_decay_factor_array(days_since)

        # 검증
        self.assertAlmostEqual(decays[0], 1.0, places=5)  # 0일: 1.0
        self.assertAlmostEqual(decays[1], 0.5, places=5)  # 7일: 0.5
        self.assertAlmostEqual(decays[2], 0.25, places=5)  # 14일: 0.25


class DataLoaderCacheTests(IsolatedRedisTestClient, BaseLectureTest):
    """
    강의-카테고리 맵 캐시 계층 검증 테스트

    - 첫 호출: DB 로드 -> Redis 캐시 저장
    - 두 번째 호출: 메모리 캐시 히트
    - 새 인스턴스: Redis 캐시 히트
    - 역직렬화 실패: DB 폴백
    """

    def setUp(self) -> None:
        super().setUp()
        self.loader: DataLoader = DataLoader()

    def test_cache_first_call_loads_from_db(self) -> None:
        """첫 호출 시 DB 로드 테스트
        - 캐시 없음
        - DB에서 강의-카테고리 매핑 로드
        - Redis에 캐시 저장
        """
        result: Dict[int, Set[int]] = self.loader.get_lecture_category_map()

        # 결과
        self.assertIsInstance(result, dict)
        self.assertIn(self.lecture1.id, result)

    def test_cache_second_call_hits_memory_cache(self) -> None:
        """두 번째 호출 시 메모리 캐시 히트 테스트
        - 첫 호출: DB 로드 -> 메모리 캐시 저장
        - 두 번째 호출: 메모리 캐시에서 즉시 반환
        - DB 조회 없음
        """
        # 첫 호출: DB 로드
        result1: Dict[int, Set[int]] = self.loader.get_lecture_category_map()

        # 두 번째 호출: 메모리 캐시 히트
        result2: Dict[int, Set[int]] = self.loader.get_lecture_category_map()

        # 동일한 객체 참조 (메모리 캐시)
        self.assertIs(result1, result2)

    def test_cache_new_instance_hits_redis_cache(self) -> None:
        """새 인스턴스는 Redis 캐시 히트 테스트
        - 첫 인스턴스: DB 로드 -> Redis 캐시 저장
        - 새 인스턴스: Redis 캐시에서 로드
        - DB 조회 없음
        """
        # 첫 인스턴스: DB 로드
        loader1: DataLoader = DataLoader()
        result1: Dict[int, Set[int]] = loader1.get_lecture_category_map()

        # 새 인스턴스: Redis 캐시 히트
        loader2: DataLoader = DataLoader()
        result2: Dict[int, Set[int]] = loader2.get_lecture_category_map()

        self.assertEqual(result1, result2)

    def test_cache_deserialization_failure_falls_back_to_db(self) -> None:
        """캐시 역직렬화 실패 시 DB 폴백 테스트
        - Redis에 손상된 데이터 저장
        - 역직렬화 실패 -> DB에서 재로드
        """
        # 손상된 데이터 캐시에 저장
        cache.set(LECTURE_CATEGORY_MAP_CACHE_KEY, b"corrupted_data")

        # DB 폴백으로 정상 로드
        result: Dict[int, Set[int]] = self.loader.get_lecture_category_map()

        # 결과
        self.assertIsInstance(result, dict)
        self.assertIn(self.lecture1.id, result)


class DataLoaderUserInteractionsTests(IsolatedRedisTestClient, BaseLectureTest):
    """
    사용자 상호작용 로드 테스트

    - 북마크 상호작용
    - 스터디 참여 상호작용
    - 시간 감쇠 적용
    - 가입 시점 이후 강의만 점수 부여
    """

    user: Any

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.user = UserFactory.create_user()

    def setUp(self) -> None:
        super().setUp()
        self.loader: DataLoader = DataLoader()

    def _create_study_group_with_lectures(self, lecture_times: List[Tuple[CrawledLecture, datetime]]) -> StudyGroup:
        """스터디 그룹 및 강의 생성 헬퍼

        Args:
            lecture_times: [(강의, 생성 시각)] 리스트

        Returns:
            생성된 StudyGroup
        """
        study_group: StudyGroup = StudyGroup.objects.create(
            name="Test Study Group",
            introduction="Test Introduction",
            max_headcount=10,
            start_at=timezone.now(),
            end_at=timezone.now() + timedelta(days=30),
            status=StudyGroupStatus.ONGOING,
        )

        for lecture, created_at in lecture_times:
            study_lecture: StudyLecture = StudyLecture.objects.create(
                study_group=study_group,
                lecture=lecture,
            )
            # auto_now_add 우회: 수동으로 created_at 설정
            StudyLecture.objects.filter(pk=study_lecture.pk).update(created_at=created_at)

        return study_group

    def _create_group_member_with_join_time(
        self, study_group: StudyGroup, user: Any, join_time: datetime
    ) -> GroupMember:
        """그룹 멤버 생성 및 가입 시점 설정 헬퍼

        Args:
            study_group: 스터디 그룹
            user: 사용자
            join_time: 가입 시각

        Returns:
            생성된 GroupMember
        """
        member: GroupMember = GroupMember.objects.create(
            study_group=study_group,
            user=user,
        )
        # auto_now_add 우회: 수동으로 created_at 설정
        GroupMember.objects.filter(pk=member.pk).update(created_at=join_time)
        return member

    def test_load_user_interactions_bookmarks(self) -> None:
        """북마크 상호작용 로드 테스트
        - 북마크된 강의에 점수 부여
        - 시간 감쇠 적용
        """
        # 북마크 생성
        LectureBookmark.objects.create(user=self.user, lecture=self.lecture1)

        # 상호작용 로드
        interactions: Dict[Tuple[int, int], float] = self.loader._load_user_interactions(
            last_trained_at=None,
            reference_time=timezone.now(),
        )

        # 검증: (user_id, lecture_id) -> score
        self.assertIn((self.user.id, self.lecture1.id), interactions)
        self.assertGreater(interactions[(self.user.id, self.lecture1.id)], 0)

    def test_study_participation_with_member_join_time_validation(self) -> None:
        """스터디 참여 상호작용 로드 테스트
        - 그룹 가입 시점 이후 생성된 강의에만 점수 부여
        - 가입 전 강의는 제외
        - 시간 감쇠 적용
        """
        # 현재 시각 기준
        now: datetime = timezone.now()

        # 강의 생성 시각 설정
        lecture_times: List[Tuple[CrawledLecture, datetime]] = [
            (self.lecture1, now - timedelta(days=10)),  # 10일 전 생성
            (self.lecture2, now - timedelta(days=5)),  # 5일 전 생성
        ]

        # 스터디 그룹 및 강의 생성
        study_group: StudyGroup = self._create_study_group_with_lectures(lecture_times)

        # 그룹 가입 시점: 7일 전 (lecture1 이후, lecture2 이전)
        join_time: datetime = now - timedelta(days=7)
        self._create_group_member_with_join_time(study_group, self.user, join_time)

        # 상호작용 로드
        interactions: Dict[Tuple[int, int], float] = self.loader._load_user_interactions(
            last_trained_at=None,
            reference_time=now,
        )

        # 검증: lecture2만 점수 부여 (가입 후 생성)
        self.assertNotIn((self.user.id, self.lecture1.id), interactions)  # 가입 전 강의
        self.assertIn((self.user.id, self.lecture2.id), interactions)  # 가입 후 강의


class DataLoaderItemFeaturesTests(IsolatedRedisTestClient, BaseLectureTest):
    """
    아이템 피처 로드 테스트

    - 강의별 피처 계산
    - 캐시 활용
    """

    def setUp(self) -> None:
        super().setUp()
        self.loader: DataLoader = DataLoader()

    def test_get_item_features_returns_dict(self) -> None:
        """아이템 피처 반환 테스트
        - 강의 ID를 키로 하는 딕셔너리 반환
        """
        # 상호작용 데이터 생성
        all_interactions: Dict[Tuple[int, int], float] = {
            (1, self.lecture1.id): 1.0,
            (1, self.lecture2.id): 0.5,
        }

        # 아이템 피처 로드
        features: Dict[Tuple[int, int], float] = self.loader._load_item_features(
            all_interactions=all_interactions,
            last_trained_at=None,
        )

        # 검증
        self.assertIsInstance(features, dict)


class DataLoaderSearchInteractionsTests(IsolatedRedisTestClient, BaseLectureTest):
    """
    검색 상호작용 테스트

    - 검색 로그 기반 점수 부여
    - 시간 감쇠 적용
    """

    user: Any

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.user = UserFactory.create_user()

    def setUp(self) -> None:
        super().setUp()
        self.loader: DataLoader = DataLoader()

    def test_load_search_interactions(self) -> None:
        """검색 상호작용 로드 테스트
        - 검색 키워드와 강의 제목 매칭
        - 점수 부여
        """
        # 검색 로그 생성
        LectureSearchLog.objects.create(
            user=self.user,
            keyword=self.lecture1.title[:10],  # 강의 제목 일부
        )

        # 검색 상호작용 로드
        interactions: Dict[Tuple[int, int], float] = self.loader._load_search_interactions(
            last_trained_at=None,
            reference_time=timezone.now(),
        )

        self.assertIsInstance(interactions, dict)


class DataLoaderMatrixBuildTests(IsolatedRedisTestClient, BaseLectureTest):
    """
    사용자-강의 행렬 구축 테스트

    - Full Fit 모드
    - Partial Fit 모드
    - 신규 사용자 감지
    - 행렬 정규화
    """

    user: Any

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.user = UserFactory.create_user()

    def setUp(self) -> None:
        super().setUp()
        self.loader: DataLoader = DataLoader()

    def test_full_fit_builds_complete_matrix(self) -> None:
        """Full Fit 모드: 전체 행렬 구축 테스트
        - 모든 사용자/강의 포함
        - 상호작용 점수 반영
        """
        # 북마크 생성
        LectureBookmark.objects.create(user=self.user, lecture=self.lecture1)

        # 행렬 구축
        result: MatrixBundleExtended = self.loader.build_user_item_matrix(
            existing_users=None,
            last_trained_at=None,
            normalize_rows=True,
            return_format="csr",
        )

        # 검증
        self.assertIsNotNone(result)
        if result is not None:
            matrix, user_to_idx, lecture_to_idx, users, lectures, is_new_user = result

            # 행렬 shape 확인
            self.assertEqual(matrix.shape[0], len(users))
            self.assertEqual(matrix.shape[1], len(lectures))

            # 매핑 확인
            self.assertIn(self.user.id, user_to_idx)
            self.assertIn(self.lecture1.id, lecture_to_idx)

    def test_partial_fit_detects_new_user(self) -> None:
        """Partial Fit 모드: 신규 사용자 감지 테스트
        - 기존 사용자 목록에 없는 사용자 감지
        - is_new_user 플래그 True 반환
        """
        # 신규 사용자 생성
        new_user: Any = UserFactory.create_user(
            email="newuser@example.com",
            password="passsword",
            nickname="nickkname",
            name="name",
            phone_number="010-0101-0100",
            gender="FEMALE",
        )

        # 북마크 생성
        LectureBookmark.objects.create(user=new_user, lecture=self.lecture1)

        # Partial Fit 모드
        existing_users: List[int] = [self.user.id]
        last_trained_at: datetime = timezone.now() - timedelta(days=1)

        result: MatrixBundleExtended = self.loader.build_user_item_matrix(
            existing_users=existing_users,
            last_trained_at=last_trained_at,
            normalize_rows=True,
            return_format="csr",
        )

        # 검증
        self.assertIsNotNone(result)
        if result is not None:
            _, _, _, _, _, is_new_user = result
            self.assertTrue(is_new_user)

    def test_matrix_normalization_applied(self) -> None:
        """행렬 정규화 적용 테스트
        - 각 행의 합이 1.0
        """
        # 북마크 생성
        LectureBookmark.objects.create(user=self.user, lecture=self.lecture1)

        # 행렬 구축 (정규화 적용)
        result: MatrixBundleExtended = self.loader.build_user_item_matrix(
            existing_users=None,
            last_trained_at=None,
            normalize_rows=True,
            return_format="csr",
        )

        # 검증
        self.assertIsNotNone(result)
        if result is not None:
            matrix, _, _, _, _, _ = result

            # 각 행의 합이 1.0인지 확인
            row_sums: np.ndarray = np.array(matrix.sum(axis=1)).flatten()
            for row_sum in row_sums:
                if row_sum > 0:
                    self.assertAlmostEqual(row_sum, 1.0, places=5)

    def test_coo_format_return(self) -> None:
        """return_format='coo' 지정 시 COO 행렬 반환 테스트
        - COO 형식으로 반환
        """
        # 북마크 생성
        LectureBookmark.objects.create(user=self.user, lecture=self.lecture1)

        # 행렬 구축 (COO 형식)
        result: MatrixBundleExtended = self.loader.build_user_item_matrix(
            existing_users=None,
            last_trained_at=None,
            normalize_rows=True,
            return_format="coo",
        )

        # 검증
        self.assertIsNotNone(result)
        if result is not None:
            matrix, _, _, _, _, _ = result
            self.assertIsInstance(matrix, coo_matrix)

    def test_empty_data_returns_none_for_partial_fit(self) -> None:
        """Partial Fit에서 신규 데이터 없을 시 None 반환 테스트
        - last_trained_at 이후 데이터 없음
        - None 반환
        """
        # 기존 사용자 목록
        existing_users: List[int] = [self.user.id]
        # 미래 시점 (신규 데이터 없음)
        last_trained_at: datetime = timezone.now() + timedelta(days=1)

        # 행렬 구축 시도
        result: MatrixBundleExtended = self.loader.build_user_item_matrix(
            existing_users=existing_users,
            last_trained_at=last_trained_at,
            normalize_rows=True,
            return_format="csr",
        )

        # 검증: None 반환
        self.assertIsNone(result)
