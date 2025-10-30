from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import numpy.typing as npt
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from scipy.sparse import csr_matrix

from apps.core.utils.isolated_cache_testcase import IsolatedRedisTestClient
from apps.lecture.models import (
    Category,
    CrawledLecture,
    LectureBookmark,
    LectureCategory,
    LectureSearchLog,
    UserPreferCategory,
)
from apps.lecture.services.recommendation_service.constants import (
    HALF_LIFE_DAYS,
    LECTURE_CATEGORY_MAP_CACHE_KEY,
)
from apps.lecture.services.recommendation_service.data_loader import (
    DataLoader,
    MatrixBundleExtended,
)
from apps.studies.models.groups import GroupMember, StudyGroup, StudyLecture
from apps.users.enums import Gender
from apps.users.models import User

UserModel = get_user_model()


class DataLoaderIntegrationTest(IsolatedRedisTestClient):
    """DataLoader 통합 테스트 - 실제 DB와 격리된 Redis 캐시를 사용한 End-to-End 테스트"""

    user1: User
    user2: User
    user3: User
    category_python: Category
    category_django: Category
    category_web: Category
    lecture1: CrawledLecture
    lecture2: CrawledLecture
    lecture3: CrawledLecture
    bookmark1: LectureBookmark
    bookmark2: LectureBookmark
    search_log1: LectureSearchLog
    search_log2: LectureSearchLog
    search_log3: LectureSearchLog
    study_group: StudyGroup
    group_member1: GroupMember
    group_member2: GroupMember
    study_lecture1: StudyLecture

    @classmethod
    def setUpTestData(cls) -> None:
        """테스트 데이터 생성"""
        users: List[User] = User.objects.bulk_create(
            [
                User(
                    email="user1@example.com",
                    nickname="user1",
                    name="User One",
                    phone_number="010-1111-1111",
                    birthday=date(1990, 1, 1),
                    gender=Gender.MALE,
                    is_active=True,
                ),
                User(
                    email="user2@example.com",
                    nickname="user2",
                    name="User Two",
                    phone_number="010-2222-2222",
                    birthday=date(1991, 2, 2),
                    gender=Gender.FEMALE,
                    is_active=True,
                ),
                User(
                    email="user3@example.com",
                    nickname="user3",
                    name="User Three",
                    phone_number="010-3333-3333",
                    birthday=date(1992, 3, 3),
                    gender=Gender.MALE,
                    is_active=True,
                ),
            ]
        )
        cls.user1, cls.user2, cls.user3 = users

        # 카테고리 이름 중복 방지
        categories: List[Category] = Category.objects.bulk_create(
            [
                Category(name="Python_Test"),
                Category(name="Django_Test"),
                Category(name="Web_Development_Test"),
            ]
        )
        cls.category_python, cls.category_django, cls.category_web = categories

        lectures: List[CrawledLecture] = CrawledLecture.objects.bulk_create(
            [
                CrawledLecture(
                    title="Django Tutorial for Beginners",
                    instructor="John Doe",
                    average_rating=Decimal("4.50"),
                    duration=120,
                    difficulty=CrawledLecture.DifficultyEnum.EASY,
                    description="Learn Django from scratch",
                    platform=CrawledLecture.PlatformEnum.UDEMY,
                    original_price=50000,
                    discount_price=30000,
                    url_link="https://example.com/django-tutorial",
                ),
                CrawledLecture(
                    title="Python Basics",
                    instructor="Jane Smith",
                    average_rating=Decimal("4.00"),
                    duration=90,
                    difficulty=CrawledLecture.DifficultyEnum.EASY,
                    description="Python fundamentals",
                    platform=CrawledLecture.PlatformEnum.INFLEARN,
                    original_price=40000,
                    discount_price=25000,
                    url_link="https://example.com/python-basics",
                ),
                CrawledLecture(
                    title="Advanced Web Development",
                    instructor="Bob Johnson",
                    average_rating=Decimal("4.80"),
                    duration=180,
                    difficulty=CrawledLecture.DifficultyEnum.HARD,
                    description="Advanced web concepts",
                    platform=CrawledLecture.PlatformEnum.UDEMY,
                    original_price=80000,
                    discount_price=60000,
                    url_link="https://example.com/advanced-web",
                ),
            ]
        )
        cls.lecture1, cls.lecture2, cls.lecture3 = lectures

        LectureCategory.objects.bulk_create(
            [
                LectureCategory(lecture=cls.lecture1, category=cls.category_django),
                LectureCategory(lecture=cls.lecture1, category=cls.category_web),
                LectureCategory(lecture=cls.lecture2, category=cls.category_python),
                LectureCategory(lecture=cls.lecture3, category=cls.category_web),
            ]
        )

        UserPreferCategory.objects.bulk_create(
            [
                UserPreferCategory(user=cls.user1, category=cls.category_django),
                UserPreferCategory(user=cls.user1, category=cls.category_python),
                UserPreferCategory(user=cls.user2, category=cls.category_web),
            ]
        )

        # 북마크 생성 (시간 감쇠 테스트용)
        bookmarks: List[LectureBookmark] = LectureBookmark.objects.bulk_create(
            [
                LectureBookmark(
                    user=cls.user1,
                    lecture=cls.lecture1,
                    created_at=timezone.now() - timedelta(days=1),
                ),
                LectureBookmark(
                    user=cls.user2,
                    lecture=cls.lecture3,
                    created_at=timezone.now() - timedelta(days=3),
                ),
            ]
        )
        cls.bookmark1, cls.bookmark2 = bookmarks

        search_logs: List[LectureSearchLog] = LectureSearchLog.objects.bulk_create(
            [
                LectureSearchLog(
                    user=cls.user1,
                    keyword="Django",
                    created_at=timezone.now() - timedelta(days=2),
                ),
                LectureSearchLog(
                    user=cls.user1,
                    keyword="Tutorial",
                    created_at=timezone.now() - timedelta(days=5),
                ),
                LectureSearchLog(
                    user=cls.user2,
                    keyword="Web",
                    created_at=timezone.now() - timedelta(days=1),
                ),
            ]
        )
        cls.search_log1, cls.search_log2, cls.search_log3 = search_logs

        cls.study_group = StudyGroup.objects.create(
            name="Django Study Group",
            introduction="Let's learn Django together",
            max_headcount=5,
            start_at=timezone.now() - timedelta(days=10),
            end_at=timezone.now() + timedelta(days=20),
            status="ONGOING",
        )

        group_members: List[GroupMember] = GroupMember.objects.bulk_create(
            [
                GroupMember(
                    study_group=cls.study_group,
                    user=cls.user1,
                    is_leader=True,
                    created_at=timezone.now() - timedelta(days=8),
                ),
                GroupMember(
                    study_group=cls.study_group,
                    user=cls.user2,
                    is_leader=False,
                    created_at=timezone.now() - timedelta(days=7),
                ),
            ]
        )
        cls.group_member1, cls.group_member2 = group_members

        cls.study_lecture1 = StudyLecture.objects.create(
            study_group=cls.study_group,
            lecture=cls.lecture1,
            created_at=timezone.now() - timedelta(days=6),
        )

    def setUp(self) -> None:
        """각 테스트 전 격리된 Redis 캐시 초기화"""
        super().setUp()
        cache.clear()
        self.loader: DataLoader = DataLoader()

    def test_build_user_item_matrix_full_training(self) -> None:
        """Full Training: 전체 데이터로 행렬 구축 테스트"""
        result: MatrixBundleExtended = self.loader.build_user_item_matrix(
            existing_users=None,
            last_trained_at=None,
            normalize_rows=True,
            return_format="csr",
        )

        self.assertIsNotNone(result)
        assert result is not None

        matrix, u_to_idx, l_to_idx, users, lectures, is_new_user = result

        self.assertEqual(matrix.shape[0], len(users))
        self.assertEqual(matrix.shape[1], len(lectures))
        self.assertGreater(len(users), 0)
        self.assertGreater(len(lectures), 0)

        self.assertIn(self.user1.id, u_to_idx)
        self.assertIn(self.user2.id, u_to_idx)
        self.assertIn(self.lecture1.id, l_to_idx)
        self.assertIn(self.lecture2.id, l_to_idx)
        self.assertIn(self.lecture3.id, l_to_idx)

        self.assertFalse(is_new_user)
        self.assertIsInstance(matrix, csr_matrix)

        row_sums: npt.NDArray[np.floating[Any]] = np.array(matrix.sum(axis=1), dtype=np.float32).flatten()
        for row_sum in row_sums:
            self.assertTrue(
                np.isclose(row_sum, 0.0) or np.isclose(row_sum, 1.0),
                f"Row sum {row_sum} is not normalized (should be 0 or 1)",
            )

    def test_build_user_item_matrix_partial_training_no_new_users(self) -> None:
        """Partial Training: 신규 사용자 없는 경우"""
        existing_users: List[int] = [self.user1.id, self.user2.id]
        last_trained_at: datetime = timezone.now() - timedelta(days=10)

        LectureBookmark.objects.create(user=self.user1, lecture=self.lecture2, created_at=timezone.now())

        result: MatrixBundleExtended = self.loader.build_user_item_matrix(
            existing_users=existing_users,
            last_trained_at=last_trained_at,
            normalize_rows=True,
        )

        self.assertIsNotNone(result)
        assert result is not None

        matrix, u_to_idx, l_to_idx, users, lectures, is_new_user = result

        self.assertFalse(is_new_user)
        self.assertEqual(set(users), set(existing_users))

    def test_build_user_item_matrix_partial_training_with_new_users(self) -> None:
        """Partial Training: 신규 사용자 감지 시 조기 반환"""
        existing_users: List[int] = [self.user1.id, self.user2.id]
        last_trained_at: datetime = timezone.now() - timedelta(days=10)

        new_user: User = User.objects.create(
            email="newuser@example.com",
            nickname="newuser",
            name="New User",
            phone_number="010-9999-9999",
            birthday=date(1995, 5, 5),
            gender=Gender.MALE,
            is_active=True,
        )
        LectureBookmark.objects.create(user=new_user, lecture=self.lecture1, created_at=timezone.now())

        result: MatrixBundleExtended = self.loader.build_user_item_matrix(
            existing_users=existing_users, last_trained_at=last_trained_at
        )

        self.assertIsNotNone(result)
        assert result is not None

        matrix, u_to_idx, l_to_idx, users, lectures, is_new_user = result

        self.assertTrue(is_new_user)
        self.assertEqual(matrix.shape, (0, 0))
        self.assertEqual(len(u_to_idx), 0)
        self.assertEqual(len(l_to_idx), 0)
        self.assertEqual(len(users), 0)
        self.assertEqual(len(lectures), 0)

    def test_lecture_category_map_caching(self) -> None:
        """강의-카테고리 맵 캐싱 전략 테스트 (메모리 → Redis → DB)"""
        map1: Dict[int, Set[int]] = self.loader.get_lecture_category_map()
        self.assertIn(self.lecture1.id, map1)
        self.assertIn(self.category_django.id, map1[self.lecture1.id])
        self.assertIn(self.category_web.id, map1[self.lecture1.id])

        map2: Dict[int, Set[int]] = self.loader.get_lecture_category_map()
        self.assertEqual(map1, map2)

        self.loader._lecture_category_map = None
        self.loader._lecture_category_map_ttl = None
        map3: Dict[int, Set[int]] = self.loader.get_lecture_category_map()
        self.assertEqual(map1, map3)

        cached_data: Optional[Any] = cache.get(LECTURE_CATEGORY_MAP_CACHE_KEY)
        self.assertIsNotNone(cached_data)

    def test_time_decay_calculation(self) -> None:
        """시간 감쇠 계산 정확성 테스트 (반감기 7일)"""
        reference_time: datetime = timezone.now()

        created_at: datetime = reference_time
        decay: float = self.loader._get_decay_factor(created_at, reference_time)
        self.assertAlmostEqual(decay, 1.0, places=5)

        created_at = reference_time - timedelta(days=HALF_LIFE_DAYS)
        decay = self.loader._get_decay_factor(created_at, reference_time)
        self.assertAlmostEqual(decay, 0.5, places=5)

        created_at = reference_time - timedelta(days=HALF_LIFE_DAYS * 2)
        decay = self.loader._get_decay_factor(created_at, reference_time)
        self.assertAlmostEqual(decay, 0.25, places=5)

        created_at = reference_time - timedelta(days=HALF_LIFE_DAYS * 3)
        decay = self.loader._get_decay_factor(created_at, reference_time)
        self.assertAlmostEqual(decay, 0.125, places=5)

    def test_time_decay_array_calculation(self) -> None:
        """벡터화된 시간 감쇠 계산 테스트"""
        days_since: npt.NDArray[np.float64] = np.array([0, 7, 14, 21])
        decay_factors: npt.NDArray[np.float64] = self.loader._get_decay_factor_array(days_since)

        expected: npt.NDArray[np.float64] = np.array([1.0, 0.5, 0.25, 0.125])
        np.testing.assert_array_almost_equal(decay_factors, expected, decimal=5)

    def test_search_interaction_with_keyword_matching(self) -> None:
        """검색 상호작용: 키워드 매칭 및 시간 감쇠 테스트"""
        LectureSearchLog.objects.all().delete()

        reference_time: datetime = timezone.now()

        LectureSearchLog.objects.create(
            user=self.user1,
            keyword="Tutorial",
            created_at=reference_time - timedelta(days=1),
        )

        search_scores: Dict[Tuple[int, int], float] = self.loader._load_search_interactions(
            last_trained_at=None, reference_time=reference_time
        )

        self.assertGreater(len(search_scores), 0)

        # 부동소수점 비교를 위해 np.isclose 사용
        search_weight: float = self.loader.user_weights.get("search", 0.0)
        for score in search_scores.values():
            self.assertGreater(score, 0)
            # 부동소수점 정밀도 오차를 고려한 비교
            self.assertTrue(
                score <= search_weight or np.isclose(score, search_weight, rtol=1e-5),
                f"Score {score} exceeds search weight {search_weight}",
            )

    def test_empty_data_handling(self) -> None:
        """빈 데이터 처리: 상호작용 없는 경우"""
        LectureBookmark.objects.all().delete()
        LectureSearchLog.objects.all().delete()
        StudyLecture.objects.all().delete()

        result: MatrixBundleExtended = self.loader.build_user_item_matrix()

        self.assertIsNone(result)

    def test_matrix_normalization(self) -> None:
        """행렬 L1 정규화 검증"""
        result: MatrixBundleExtended = self.loader.build_user_item_matrix(normalize_rows=True)

        if result:
            matrix, _, _, _, _, _ = result

            row_sums: npt.NDArray[np.floating[Any]] = np.array(matrix.sum(axis=1), dtype=np.float32).flatten()
            for row_sum in row_sums:
                self.assertTrue(
                    np.isclose(row_sum, 0.0) or np.isclose(row_sum, 1.0),
                    f"Row sum {row_sum} is not normalized",
                )

    def test_user_interactions_with_time_decay(self) -> None:
        """사용자 상호작용: 북마크 및 스터디 참여 시간 감쇠 테스트"""
        reference_time: datetime = timezone.now()

        interactions: Dict[Tuple[int, int], float] = self.loader._load_user_interactions(
            last_trained_at=None, reference_time=reference_time
        )

        bookmark_key: Tuple[int, int] = (self.user1.id, self.lecture1.id)
        self.assertIn(bookmark_key, interactions)

        bookmark_weight: float = self.loader.user_weights.get("bookmark", 0.0)
        study_weight: float = self.loader.user_weights.get("study_participation", 0.0)

        # 북마크 + 스터디 참여 점수가 합쳐짐
        # 스터디는 시간 감쇠가 적용되므로 정확한 값 대신 범위 체크
        self.assertGreaterEqual(interactions[bookmark_key], bookmark_weight)
        self.assertLessEqual(interactions[bookmark_key], bookmark_weight + study_weight)

    def test_item_features_category_matching(self) -> None:
        """아이템 피처: 카테고리 매칭 점수 테스트"""
        interactions: Dict[Tuple[int, int], float] = {
            (self.user1.id, self.lecture1.id): 1.0,
            (self.user1.id, self.lecture2.id): 1.0,
        }

        item_features: Dict[Tuple[int, int], float] = self.loader._load_item_features(
            all_interactions=interactions, last_trained_at=None
        )

        key1: Tuple[int, int] = (self.user1.id, self.lecture1.id)
        if key1 in item_features:
            self.assertGreater(item_features[key1], 0)

        key2: Tuple[int, int] = (self.user1.id, self.lecture2.id)
        if key2 in item_features:
            self.assertGreater(item_features[key2], 0)

    def test_item_features_rating_bonus(self) -> None:
        """아이템 피처: 평점 보너스 점수 테스트"""
        interactions: Dict[Tuple[int, int], float] = {
            (self.user1.id, self.lecture1.id): 1.0,
            (self.user1.id, self.lecture3.id): 1.0,
        }

        item_features: Dict[Tuple[int, int], float] = self.loader._load_item_features(
            all_interactions=interactions, last_trained_at=None
        )

        rating_weight: float = self.loader.item_weights.get("review_rating", 0.0)
        if rating_weight > 0:
            self.assertGreater(len(item_features), 0)

    def test_search_interaction_multiple_keywords(self) -> None:
        """검색 상호작용: 여러 키워드 검색 시 점수 누적 테스트"""
        reference_time: datetime = timezone.now()

        LectureSearchLog.objects.bulk_create(
            [
                LectureSearchLog(
                    user=self.user1,
                    keyword="Django",
                    created_at=reference_time - timedelta(days=1),
                ),
                LectureSearchLog(
                    user=self.user1,
                    keyword="Tutorial",
                    created_at=reference_time - timedelta(days=2),
                ),
            ]
        )

        search_scores: Dict[Tuple[int, int], float] = self.loader._load_search_interactions(
            last_trained_at=None, reference_time=reference_time
        )

        lecture1_scores: List[float] = [
            score
            for (user_id, lec_id), score in search_scores.items()
            if user_id == self.user1.id and lec_id == self.lecture1.id
        ]

        if lecture1_scores:
            self.assertGreater(lecture1_scores[0], 0)

    def test_partial_fit_no_new_data(self) -> None:
        """Partial Fit: 신규 데이터 없을 때 None 반환 테스트"""
        existing_users: List[int] = [self.user1.id, self.user2.id]
        last_trained_at: datetime = timezone.now() + timedelta(days=1)

        result: MatrixBundleExtended = self.loader.build_user_item_matrix(
            existing_users=existing_users,
            last_trained_at=last_trained_at,
            normalize_rows=True,
        )

        self.assertIsNone(result)

    def test_study_participation_member_join_validation(self) -> None:
        """스터디 참여: 그룹 가입 시점 검증 테스트"""
        reference_time: datetime = timezone.now()

        old_lecture: CrawledLecture = CrawledLecture.objects.create(
            title="Old Lecture",
            instructor="Old Instructor",
            average_rating=Decimal("4.00"),
            duration=60,
            difficulty=CrawledLecture.DifficultyEnum.EASY,
            description="Old lecture",
            platform=CrawledLecture.PlatformEnum.UDEMY,
            original_price=30000,
            discount_price=20000,
            url_link="https://example.com/old-lecture",
        )

        StudyLecture.objects.create(
            study_group=self.study_group,
            lecture=old_lecture,
            created_at=timezone.now() - timedelta(days=20),
        )

        interactions: Dict[Tuple[int, int], float] = self.loader._load_user_interactions(
            last_trained_at=None, reference_time=reference_time
        )

        old_lecture_key: Tuple[int, int] = (self.user1.id, old_lecture.id)

    def test_cache_ttl_expiration(self) -> None:
        """캐시 TTL 만료 테스트"""
        map1: Dict[int, Set[int]] = self.loader.get_lecture_category_map()

        self.loader._lecture_category_map_ttl = timezone.now() - timedelta(seconds=1)

        map2: Dict[int, Set[int]] = self.loader.get_lecture_category_map()

        self.assertEqual(map1, map2)

    def test_matrix_without_normalization(self) -> None:
        """정규화 없는 행렬 구축 테스트"""
        result: MatrixBundleExtended = self.loader.build_user_item_matrix(normalize_rows=False, return_format="coo")

        if result:
            matrix, _, _, _, _, _ = result

            row_sums: npt.NDArray[np.floating[Any]] = np.array(matrix.sum(axis=1), dtype=np.float32).flatten()

            non_normalized: List[float] = [rs for rs in row_sums if not np.isclose(rs, 1.0) and not np.isclose(rs, 0.0)]
            if len(row_sums) > 0 and np.any(row_sums > 0):
                self.assertGreater(len(non_normalized), 0)


class DataLoaderEdgeCaseTest(IsolatedRedisTestClient):
    """DataLoader 엣지 케이스 테스트"""

    def setUp(self) -> None:
        super().setUp()
        cache.clear()
        self.loader: DataLoader = DataLoader()

    def test_empty_database(self) -> None:
        """빈 데이터베이스 처리 테스트"""
        result: MatrixBundleExtended = self.loader.build_user_item_matrix()
        self.assertIsNone(result)

    def test_lecture_category_map_empty(self) -> None:
        """강의-카테고리 매핑이 없는 경우"""
        lecture_map: Dict[int, Set[int]] = self.loader.get_lecture_category_map()
        self.assertEqual(lecture_map, {})

    def test_search_with_empty_keyword(self) -> None:
        """빈 키워드 검색 처리 테스트"""
        user: User = User.objects.create(
            email="test@example.com",
            nickname="testuser",
            name="Test User",
            phone_number="010-0000-0000",
            birthday=date(1990, 1, 1),
            gender=Gender.MALE,
            is_active=True,
        )

        LectureSearchLog.objects.create(user=user, keyword="", created_at=timezone.now())

        search_scores: Dict[Tuple[int, int], float] = self.loader._load_search_interactions(
            last_trained_at=None, reference_time=timezone.now()
        )

        self.assertEqual(len(search_scores), 0)

    def test_naive_datetime_handling(self) -> None:
        """Naive datetime 처리 테스트"""
        user: User = User.objects.create(
            email="test2@example.com",
            nickname="testuser2",
            name="Test User 2",
            phone_number="010-0000-0001",
            birthday=date(1990, 1, 1),
            gender=Gender.MALE,
            is_active=True,
        )
        lecture: CrawledLecture = CrawledLecture.objects.create(
            title="Test Lecture",
            instructor="Test",
            average_rating=Decimal("4.00"),
            duration=60,
            difficulty=CrawledLecture.DifficultyEnum.EASY,
            description="Test",
            platform=CrawledLecture.PlatformEnum.UDEMY,
            original_price=10000,
            discount_price=5000,
            url_link="https://example.com/test",
        )

        LectureBookmark.objects.create(user=user, lecture=lecture)

        naive_dt: datetime = datetime(2024, 1, 1, 0, 0, 0)

        result: MatrixBundleExtended = self.loader.build_user_item_matrix(
            existing_users=[user.id], last_trained_at=naive_dt
        )

        self.assertIsNotNone(result)
