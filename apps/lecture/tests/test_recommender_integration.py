from typing import Any
from unittest.mock import patch

import numpy as np
from django.contrib.auth import get_user_model
from django.core.cache import cache
from implicit.als import AlternatingLeastSquares  # type: ignore
from scipy.sparse import csr_matrix

from apps.core.utils.isolated_cache_testcase import IsolatedRedisTestClient
from apps.lecture.models import (
    LectureBookmark,
    UserPreferCategory,
)
from apps.lecture.services.recommendation_service.constants import (
    POPULAR_LECTURE_CACHE_KEY,
)
from apps.lecture.services.recommendation_service.recommender import (
    RecommendationService,
)
from apps.lecture.tests.base_lecture import BaseLectureTest

User = get_user_model()


class RecommendationServiceIntegrationTests(IsolatedRedisTestClient, BaseLectureTest):
    """추천 서비스 통합 테스트 - 실제 사용 시나리오 검증"""

    user: Any

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.user = User.objects.create_user(
            email="integrationt@example.com",
            password="integrate",
            nickname="integ_user",
            name="Integration Test",
            phone_number="010-9999-9999",
            gender="M",
            birthday="1990-01-01",
        )

        # 사용자 선호 카테고리 설정
        UserPreferCategory.objects.create(user=cls.user, category=cls.category1)

    def setUp(self) -> None:
        super().setUp()
        self.service = RecommendationService()

    def test_recommend_lectures_end_to_end_with_model(self) -> None:
        """
        모델 기반 추천 시스템 전체 워크플로우 테스트

        시나리오:
        1. 모델이 로드되어 있음
        2. 사용자가 모델에 존재
        3. 추천 실행 -> 결과 반환
        """
        # Given: ALS 모델이 로드되어 있고 사용자가 모델에 존재
        real_model = AlternatingLeastSquares(factors=10)  # 모델 설정 (10개 잠재 요인)
        self.service._model = real_model  # 서비스에 모델 주입
        # 사용자 ID -> 행렬 인덱스 매핑
        self.service._user_to_idx = {self.user.id: 0}
        # 강의 ID -> 행렬 인덱스 매핑 (양방향)
        self.service._lecture_to_idx = {self.lecture1.id: 0, self.lecture2.id: 1}
        self.service._lecture_idx_to_id = {0: self.lecture1.id, 1: self.lecture2.id}
        # 사용자-강의 상호작용 행렬 (10명 사용자 x 20개 강의)
        self.service._user_items_matrix = csr_matrix((10, 20), dtype=np.float32)

        # When: recommend 메서드를 모킹하여 추천 실행
        with patch.object(real_model, "recommend") as mock_recommend:
            mock_indices = np.array([0, 1])  # 추천 강의 인덱스
            mock_scores = np.array([0.9, 0.7])  # 추천 점수 (높을수록 좋음)
            mock_recommend.return_value = (mock_indices, mock_scores)

            # 추천 실행 (최대 5개)
            result = self.service.recommend_lectures(self.user.id, 5)

        # Then: 추천 결과가 반환됨
        self.assertIsNotNone(result)  # 결과 존재
        self.assertGreater(result.count(), 0)  # 최소 1개 이상 추천

        # 추천된 강의가 실제 강의 목록에 포함되어 있는지 확인
        result_ids = list(result.values_list("id", flat=True))
        self.assertIn(self.lecture1.id, result_ids)

    def test_recommend_lectures_end_to_end_category_fallback(self) -> None:
        """
        모델 로드 실패 시 카테고리 기반 추천으로 폴백 테스트

        폴백 전략:
        1차: 모델 기반 추천
        2차: 카테고리 기반 추천 (사용자 선호 카테고리)
        3차: 인기 강의 추천
        """
        # Given: 모델이 로드되지 않은 상태
        with patch.object(self.service, "_ensure_model_loaded", return_value=False):
            # When: 추천 실행
            result = self.service.recommend_lectures(self.user.id, 5)

        # Then: 카테고리 기반 추천 결과 반환
        # setUpTestData에서 설정한 category1 기반 추천
        self.assertIsNotNone(result)
        self.assertGreater(result.count(), 0)

    def test_recommend_lectures_end_to_end_popular_fallback(self) -> None:
        """
        모델 실패 + 선호 카테고리 없음 -> 인기 강의 추천 테스트

        최종 폴백 시나리오:
        - 모델 로드 실패
        - 사용자 선호 카테고리 없음
        - 인기 강의로 폴백
        """
        # Given: 모델 로드 실패 & 사용자 선호 카테고리 없음
        UserPreferCategory.objects.filter(user=self.user).delete()  # 선호 카테고리 삭제

        # 모델 로드 실패
        with patch.object(self.service, "_ensure_model_loaded", return_value=False):
            # When: 추천 실행
            result = self.service.recommend_lectures(self.user.id, 5)

        # Then: 인기 강의 폴백으로 추천 결과 반환
        self.assertIsNotNone(result)

    def test_recommend_lectures_excludes_bookmarked_lectures(self) -> None:
        """
        이미 북마크한 강의는 추천에서 제외 테스트

        - 사용자가 이미 관심 표시한 강의는 재추천하지 않음
        - 새로운 발견 기회 제공
        """
        # Given: lecture1 북마크
        LectureBookmark.objects.create(user=self.user, lecture=self.lecture1)

        # 모델 설정
        real_model = AlternatingLeastSquares(factors=10)
        self.service._model = real_model
        self.service._user_to_idx = {self.user.id: 0}
        self.service._lecture_to_idx = {self.lecture1.id: 0, self.lecture2.id: 1}
        self.service._lecture_idx_to_id = {0: self.lecture1.id, 1: self.lecture2.id}
        self.service._user_items_matrix = csr_matrix((10, 20), dtype=np.float32)

        # When: 추천 실행 - lecture1과 lecture2 모두 추천하도록 모킹
        with patch.object(real_model, "recommend") as mock_recommend:
            # 두 강의 모두 추천하지만, 북마크 필터링으로 lecture1은 제외되어야 함
            mock_indices = np.array([0, 1])  # lecture1, lecture2
            mock_scores = np.array([0.9, 0.7])
            mock_recommend.return_value = (mock_indices, mock_scores)

            result = self.service.recommend_lectures(self.user.id, 5)

        # Then: lecture1은 북마크되어 제외, lecture2만 반환
        result_ids = list(result.values_list("id", flat=True))
        self.assertNotIn(self.lecture1.id, result_ids)  # 북마크된 강의 제외
        self.assertIn(self.lecture2.id, result_ids)  # 북마크 안된 강의 포함

    def test_recommend_lectures_with_metadata_enrichment(self) -> None:
        """
        추천 결과에 추가 메타데이터 포함 테스트

        메타데이터:
        - 평균 평점 (average_rating)
        - 리뷰 수
        - 기타 강의 정보
        """
        # Given: 모델 설정
        real_model = AlternatingLeastSquares(factors=10)
        self.service._model = real_model
        self.service._user_to_idx = {self.user.id: 0}
        self.service._lecture_to_idx = {self.lecture1.id: 0}
        self.service._lecture_idx_to_id = {0: self.lecture1.id}
        self.service._user_items_matrix = csr_matrix((10, 20), dtype=np.float32)

        # When: 추천 실행
        with patch.object(real_model, "recommend") as mock_recommend:
            mock_indices = np.array([0])  # lecture1만 추천
            mock_scores = np.array([0.9])
            mock_recommend.return_value = (mock_indices, mock_scores)

            result = self.service.recommend_lectures(self.user.id, 5)

        # Then: 메타데이터(결과에 평점 정보가 포함됨) 포함 확인
        self.assertIsNotNone(result)
        self.assertGreater(result.count(), 0)

        # 첫 번째 강의의 평점 정보 확인
        first_lecture = result.first()
        if first_lecture is not None:
            # average_rating 필드가 존재하고 값이 있어야 함
            self.assertIsNotNone(first_lecture.average_rating)

    def test_cache_usage_in_recommendation_flow(self) -> None:
        """
        인기 강의 캐시 활용 테스트

        캐시 전략:
        - 인기 강의 목록을 Redis에 캐싱
        - DB 조회 최소화로 성능 향상
        - 캐시 키: POPULAR_LECTURE_CACHE_KEY
        """
        # Given: 인기 강의가 캐시에 저장됨
        cached_ids = [self.lecture2.id, self.lecture1.id]  # 인기 순서
        cache.set(POPULAR_LECTURE_CACHE_KEY, cached_ids)

        # 모델 로드 실패 + 선호 카테고리 없음 시나리오
        with patch.object(self.service, "_ensure_model_loaded", return_value=False):
            UserPreferCategory.objects.filter(user=self.user).delete()

            # When: 추천 실행 (최대 2개)
            result = self.service.recommend_lectures(self.user.id, 2)

        # Then: 캐시된 인기 강의 반환
        self.assertIsNotNone(result)
        result_ids = list(result.values_list("id", flat=True))
        self.assertEqual(len(result_ids), 2)  # 요청한 개수만큼 반환
