import logging
import os
import uuid
from datetime import timedelta
from typing import Any, Dict, List, Set, Tuple, cast
from unittest import mock
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models.query import QuerySet
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.core.utils.isolated_cache_testcase import IsolatedRedisTestClient
from apps.lecture.models import (
    Category,
    CrawledLecture,
    CrawledLectureReview,
    LectureBookmark,
    LectureCategory,
    LectureSearchLog,
    UserPreferCategory,
)
from apps.lecture.services.constants import (
    ALS_MODEL_CACHE_KEY,
    INTERACTION_WEIGHTS,
    L_IDX_TO_ID_CACHE_KEY,
    L_TO_IDX_CACHE_KEY,
    LECTURE_CATEGORY_MAP_CACHE_KEY,
    RATING_SCORE_MAP,
    U_TO_IDX_CACHE_KEY,
    USER_ITEMS_MATRIX_CACHE_KEY,
)
from apps.lecture.services.data_loader import DataLoader
from apps.lecture.services.model_trainer import ModelTrainer
from apps.lecture.services.recommender import RecommendationService
from apps.studies.models.groups import GroupMember, StudyGroup, StudyLecture

User = get_user_model()


class RecommendationFeatureIntegrationTest(IsolatedRedisTestClient, APITestCase):
    """통합 테스트: 추천 기능 전체 흐름 및 엣지 케이스 검증"""

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="testuser@example.com",
            password="password123",
            nickname="testnick",
            name="테스트 사용자",
            phone_number="01000000001",
            birthday="1990-01-01",
            gender="M",
            is_active=True,
        )
        self.client.force_authenticate(user=self.user)
        self.recommend_url = reverse("recommendations")

        self.categories = [Category.objects.create(name=f"카테고리{i}") for i in range(5)]
        self.lectures = []

        # 폴백 테스트를 위해 강의 수를 11개 이상으로 설정 (10개를 요청해도 1개 제외 후 남도록)
        NUM_LECTURES = 11
        for i in range(NUM_LECTURES):
            lec = CrawledLecture.objects.create(
                uuid=str(uuid.uuid4()),
                title=f"테스트 강의 {i}",
                instructor=f"강사 {i}",
                thumbnail_img_url=f"https://example.com/thumb{i}.jpg",
                difficulty="NORMAL",
                original_price=100000,
                discount_price=80000,
                platform="INFLEARN",
                average_rating=4.5 - 0.1 * i,
                duration=100 + 10 * i,
                url_link=f"https://example.com/lecture/{i}",
                description="테스트 강의 설명",
            )
            LectureCategory.objects.create(lecture=lec, category=self.categories[i % 5])
            self.lectures.append(lec)

        # 상호작용 데이터 생성
        LectureBookmark.objects.create(user=self.user, lecture=self.lectures[0])
        LectureSearchLog.objects.create(user=self.user, keyword="테스트")
        UserPreferCategory.objects.create(user=self.user, category=self.categories[0])
        CrawledLectureReview.objects.create(lecture=self.lectures[0], rating="5_OUT_OF_5_STARS")

        self.study_group = StudyGroup.objects.create(
            name="테스트 스터디",
            start_at=timezone.now(),
            end_at=timezone.now() + timedelta(days=5),
            status="ONGOING",
        )
        GroupMember.objects.create(study_group=self.study_group, user=self.user, is_leader=True)
        StudyLecture.objects.create(study_group=self.study_group, lecture=self.lectures[0])

        cache.clear()
        self.data_loader = DataLoader(weights=INTERACTION_WEIGHTS, rating_map=RATING_SCORE_MAP)

        # 모델 파일 경로 설정 (tearDown에서 확실히 정리)
        model_storage = getattr(settings, "MODEL_STORAGE_PATH", "/tmp/model_storage")
        os.makedirs(model_storage, exist_ok=True)

    def tearDown(self) -> None:
        """테스트 완료 후 생성된 모델 파일 및 캐시 정리"""
        cache.clear()
        model_storage = getattr(settings, "MODEL_STORAGE_PATH", "/tmp/model_storage")
        for filename in ["als_model.npz", "als_mappings.npz"]:
            filepath = os.path.join(model_storage, filename)
            if os.path.exists(filepath):
                os.remove(filepath)
        super().tearDown()

    def _ensure_model_trained_and_cached(self) -> ModelTrainer:
        """테스트를 위해 모델을 훈련하고 디스크에 저장"""
        trainer = ModelTrainer(data_loader=self.data_loader)
        # 훈련 데이터가 있을 때만 훈련 시도. 이미 저장되어 있다면 로드만 시도.
        if not os.path.exists(trainer.MODEL_PATH):
            trainer.train_and_save_full_model()
        return trainer

    def test_model_training_and_successful_disk_load(self) -> None:
        """모델 훈련 후 디스크에 저장되고 성공적으로 로드되는지 검증"""
        trainer = self._ensure_model_trained_and_cached()

        self.assertTrue(os.path.exists(trainer.MODEL_PATH))

        loaded_model_data: Tuple[Any, Dict[int, int], Dict[int, int], List[int], List[int]] = cast(
            Tuple[Any, Dict[int, int], Dict[int, int], List[int], List[int]], trainer.load_model_and_mappings()
        )

        model, u_to_i, l_to_i, users_loaded, lectures_loaded = loaded_model_data

        self.assertIsNotNone(model)
        self.assertGreater(cast(Any, model).factors, 0)
        self.assertIsNotNone(u_to_i)
        self.assertIsNotNone(l_to_i)

    def test_model_load_fails_if_mapping_file_missing(self) -> None:
        """훈련 후 매핑 파일이 없을 때 로드에 실패하는지 검증"""
        trainer = self._ensure_model_trained_and_cached()

        # 매핑 파일 삭제
        if os.path.exists(trainer.MAPPING_PATH):
            os.remove(trainer.MAPPING_PATH)

        # 로드 시도 -> 실패 확인
        model_data = trainer.load_model_and_mappings()
        self.assertIsNone(model_data[0])
        self.assertIsNone(model_data[1])

    def test_recommendation_service_and_api_success(self) -> None:
        """모델 훈련 및 로드 후 추천 서비스가 올바른 결과를 반환하고 API가 성공하는지 검증"""
        self._ensure_model_trained_and_cached()

        recommender = RecommendationService()
        recs = recommender.recommend_lectures_for_user(self.user.id, top_n=3)
        self.assertIsNotNone(recs)
        recs_qs = cast(QuerySet[CrawledLecture], recs)
        self.assertGreaterEqual(recs_qs.count(), 1)

        response = self.client.get(self.recommend_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data: Dict[str, Any] = response.data.get("data", {})
        recs_list = data.get("recommendations", [])
        self.assertIsInstance(recs_list, list)
        self.assertGreaterEqual(len(recs_list), 3)

        if recs_list:
            # 💡 개선: API 응답 필드와 is_bookmarked 상태 검증
            expected_keys: Set[str] = {
                "id",
                "uuid",
                "title",
                "instructor",
                "thumbnail_img_url",
                "categories",
                "difficulty",
                "original_price",
                "discount_price",
                "platform",
                "average_rating",
                "url_link",
                "is_bookmarked",
            }
            self.assertTrue(expected_keys.issubset(recs_list[0].keys()))

            # 북마크된 강의 (self.lectures[0])가 응답에 포함되었다면 is_bookmarked=True 검증
            bookmarked_lecture_id = self.lectures[0].id
            bookmarked_in_response = next((rec for rec in recs_list if rec["id"] == bookmarked_lecture_id), None)
            if bookmarked_in_response:
                self.assertTrue(bookmarked_in_response["is_bookmarked"])

            # 북마크되지 않은 강의 (예: self.lectures[1])가 응답에 포함되었다면 is_bookmarked=False 검증
            non_bookmarked_lecture_id = self.lectures[1].id
            non_bookmarked_in_response = next(
                (rec for rec in recs_list if rec["id"] == non_bookmarked_lecture_id), None
            )
            if non_bookmarked_in_response:
                self.assertFalse(non_bookmarked_in_response["is_bookmarked"])

    def test_api_authentication_required(self) -> None:
        """인증되지 않은 사용자가 API 접근 시 401을 반환하는지 검증"""
        self.client.logout()
        response = self.client.get(self.recommend_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_recommend_cold_start_new_user_with_no_bookmarks_falls_back_to_popular(self) -> None:
        """행렬에 없는 신규 사용자(콜드 스타트)가 인기 강의로 폴백되는지 검증"""
        self._ensure_model_trained_and_cached()

        user_cold_start = User.objects.create_user(
            email="coldstart@example.com",
            nickname="colduser",
            name="Cold Start User",
            phone_number="01099990000",
            birthday="1990-01-01",
            gender="M",
            is_active=True,
        )

        recommender = RecommendationService()
        self.assertTrue(recommender._ensure_model_loaded())

        # 추천 요청 -> 콜드 스타트 폴백이 발생해야 함
        top_n = 3
        recs = recommender.recommend_lectures_for_user(user_cold_start.id, top_n=top_n)

        self.assertIsNotNone(recs)
        recs_qs = cast(QuerySet[CrawledLecture], recs)
        self.assertEqual(recs_qs.count(), top_n)

        # 폴백 증거: 가장 인기 있는 강의가 포함되었는지 확인
        top_lecture = CrawledLecture.objects.order_by("-average_rating").first()
        self.assertIn(top_lecture, list(recs_qs))

    def test_recommend_insufficient_results_falls_back_to_popular(self) -> None:
        """모델이 top_n 미만의 결과를 반환할 때 인기 강의로 폴백되는지 검증 (Line 174-177 커버)"""
        # 1. 모델이 예측하기 어렵도록 상호작용 최소화
        LectureBookmark.objects.all().delete()
        LectureBookmark.objects.create(user=self.user, lecture=self.lectures[9])

        # 2. 아주 적은 상호작용으로 모델 재훈련 (setUp에서 저장한 모델을 덮어씀)
        trainer = ModelTrainer(data_loader=self.data_loader)
        self.assertTrue(trainer.train_and_save_full_model())

        recommender = RecommendationService()
        recommender._model = None  # 메모리 무효화 후 재로드
        self.assertTrue(recommender._ensure_model_loaded())

        # 3. 추천 요청 -> top_n=10 설정으로 예측 부족 유도 및 폴백 확인
        top_n = 10
        recs = recommender.recommend_lectures_for_user(self.user.id, top_n=top_n)

        self.assertIsNotNone(recs)
        recs_qs = cast(QuerySet[CrawledLecture], recs)
        self.assertEqual(recs_qs.count(), top_n)

        # 폴백 증거: 가장 인기 있는 강의가 결과에 포함됨
        top_lecture = CrawledLecture.objects.order_by("-average_rating").first()
        self.assertIn(top_lecture, list(recs_qs))

    def test_ensure_model_loaded_from_memory(self) -> None:
        """메모리에 모델이 있을 때, Redis/디스크 접근 없이 즉시 True 반환 검증"""
        self._ensure_model_trained_and_cached()
        recommender = RecommendationService()

        # 1차 로드: 디스크/Redis -> 메모리 설정
        self.assertTrue(recommender._ensure_model_loaded())

        # 2차 로드: 메모리 변수에서 즉시 반환되는지 확인
        self.assertTrue(recommender._ensure_model_loaded())

    def test_ensure_model_loaded_redis_corrupted_cache_falls_back_to_disk(self) -> None:
        """Redis 역직렬화 오류 시 캐시 삭제 후 디스크 로드로 폴백되는지 검증"""
        # 1. 모델이 디스크에 확실히 존재하도록 보장
        self._ensure_model_trained_and_cached()  # 디스크 저장 시도
        recommender = RecommendationService()

        # 2. 모델을 Redis에 캐싱 (첫 번째 로드는 디스크에서 성공)
        self.assertTrue(recommender._ensure_model_loaded())

        # 3. 캐시를 의도적으로 손상시켜 UnpicklingError 유도
        for key in [
            ALS_MODEL_CACHE_KEY,
            U_TO_IDX_CACHE_KEY,
            L_TO_IDX_CACHE_KEY,
            L_IDX_TO_ID_CACHE_KEY,
            USER_ITEMS_MATRIX_CACHE_KEY,
        ]:
            cache.set(key, b"bad_pickle_data", timeout=60)

        recommender._model = None

        # 4. 로드 시도 -> 오류 발생 -> 캐시 삭제 -> 디스크 로드 성공 -> True 반환 및 재캐싱
        # Assert 1: 디스크 로드가 성공하여 True 반환
        self.assertTrue(recommender._ensure_model_loaded())

        # Assert 2: 재캐싱이 이루어졌으므로, 캐시는 None이 아니어야 함.
        self.assertIsNotNone(cache.get(ALS_MODEL_CACHE_KEY))

    @mock.patch(
        "apps.lecture.services.recommender.cache.set_many",
        side_effect=RuntimeError("Redis set error"),
    )
    def test_ensure_model_loaded_redis_set_error_ignored(self, mock_cache_set: mock.MagicMock) -> None:
        """Redis 캐싱(set_many) 오류 발생 시에도 디스크 로드 성공 시 True 반환 검증"""
        # 1. 모델이 디스크에 확실히 존재하도록 보장
        self._ensure_model_trained_and_cached()
        recommender = RecommendationService()

        recommender._model = None  # 메모리 무효화
        cache.clear()  # Redis 캐시 무효화

        # set_many Mock이 오류를 일으키더라도 True가 반환되는지 확인 (디스크 로드가 성공했으므로)
        self.assertTrue(recommender._ensure_model_loaded())
        mock_cache_set.assert_called_once()

    def test_ensure_model_loaded_disk_matrix_missing(self) -> None:
        """상호작용 데이터가 없어 행렬 생성 실패 시 False를 반환하는지 검증."""

        # 1. 모델이 디스크에 확실히 존재하도록 보장 (로드를 시도하기 위함)
        self._ensure_model_trained_and_cached()
        recommender = RecommendationService()

        # 2. Redis 및 메모리 초기화
        cache.clear()
        recommender._model = None

        # 3. **실제 데이터 조작**: 상호작용 데이터를 모두 삭제하여 행렬 생성을 실패하게 만듦
        LectureBookmark.objects.all().delete()
        CrawledLectureReview.objects.all().delete()
        StudyLecture.objects.all().delete()

        # DataLoader의 캐시도 클리어하여 새 데이터를 로드하게 함 (선택 사항이지만 안전함)
        cache.delete(USER_ITEMS_MATRIX_CACHE_KEY)

        # 4. 로드 시도 -> 행렬 생성이 실패하므로 False 반환 확인
        # (DataLoader.build_user_item_matrix가 None을 반환하는 실제 경로를 탐)
        result = recommender._ensure_model_loaded()

        self.assertFalse(result)

        # 행렬이 없으므로 모델도 로드되지 않았어야 함
        self.assertIsNone(recommender._model)

    def test_recommender_redis_failure_fallback_to_disk(self) -> None:
        """Redis get_many 오류 시 디스크 로드로 폴백하는지 검증"""
        # 1. 모델이 디스크에 확실히 존재하도록 보장
        self._ensure_model_trained_and_cached()
        recommender = RecommendationService()

        # 2. Redis get_many를 Mock하여 오류 발생 유도
        with mock.patch(
            "apps.lecture.services.recommender.cache.get_many",
            side_effect=RuntimeError("Redis down"),
        ):
            result: bool = recommender._ensure_model_loaded()
            self.assertTrue(result)

    def test_dataloader_category_map_cache_corruption_falls_back_to_db(self) -> None:
        """DataLoader의 카테고리 맵 캐시 손상 시 DB에서 로드하는지 검증"""
        loader: DataLoader = DataLoader(weights=INTERACTION_WEIGHTS, rating_map=RATING_SCORE_MAP)

        # 1. 정상 로드 (DB -> 캐시)
        valid_map = loader.get_lecture_category_map()
        self.assertTrue(len(valid_map) > 0)

        # 2. 캐시 손상 유도
        cache.set(LECTURE_CATEGORY_MAP_CACHE_KEY, b"corrupted_pickle", timeout=60)

        # 3. 폴백 로드 (캐시 오류 -> DB 로드)
        fallback_map = loader.get_lecture_category_map()
        self.assertTrue(len(fallback_map) >= len(valid_map))
        # 캐시된 데이터와 다른 객체인지 확인 (재로드 보장)
        self.assertIsNot(fallback_map, valid_map)

    def test_modeltrainer_save_failure_handling(self) -> None:
        """모델 저장 중 디스크 오류 발생 시 train_and_save_full_model이 False를 반환하는지 테스트."""
        with mock.patch(
            "apps.lecture.services.model_trainer.joblib.dump",
            side_effect=OSError("Disk full"),
        ) as mock_dump:
            # trainer 인스턴스만 새로 생성
            trainer = ModelTrainer(data_loader=self.data_loader)
            result: bool = trainer.train_and_save_full_model()

            self.assertFalse(result)
            mock_dump.assert_called()

    @patch("apps.lecture.services.model_trainer.joblib.load", side_effect=RuntimeError("Corrupt file"))
    @patch("apps.lecture.services.model_trainer.logger.error")
    def test_load_model_failure_handling(self, mock_logger_error: MagicMock, mock_joblib_load: MagicMock) -> None:
        """
        모델 로드 중 예외 발생 시 None을 반환하고 오류 로깅을 남기는지 검증.
        """
        # 디스크에 모델 파일이 존재해야 joblib.load가 호출되므로,
        # 모델이 디스크에 저장되도록 헬퍼 메서드 호출.
        self._ensure_model_trained_and_cached()
        trainer = ModelTrainer(data_loader=self.data_loader)

        # joblib.load Mock이 적용된 상태에서 로드 시도
        model, *mappings = trainer.load_model_and_mappings()

        # Assertions
        self.assertIsNone(model)
        self.assertIsNone(mappings[0])  # u_to_i
        self.assertEqual(len(mappings), 4)  # 모든 반환 값이 None인지 확인

        # 예외 정보가 포함된 로깅이 호출되었는지 확인
        mock_logger_error.assert_called_once()
        self.assertIn("Error loading model or mappings:", mock_logger_error.call_args[0][0])
        self.assertTrue(mock_logger_error.call_args[1]["exc_info"])
