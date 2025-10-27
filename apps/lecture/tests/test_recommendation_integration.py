# import os
# import shutil
# from datetime import timedelta
# from typing import Any, Dict, List, Tuple, cast
#
# # 필요한 Django/DRF 모듈
# from django.contrib.auth import get_user_model
# from django.core.cache import cache
# from django.db.models import QuerySet
# from django.urls import reverse
# from django.utils import timezone
# from rest_framework import status
# from rest_framework.response import Response as APIResponse
# from rest_framework.test import APIClient
#
# # Redis 격리 믹스인 임포트
# from apps.core.utils.isolated_cache_testcase import IsolatedRedisTestClient
#
# # 프로젝트 내부 모델
# from apps.lecture.models import (
#     Category,
#     CrawledLecture,
#     LectureBookmark,
#     LectureCategory,
#     LectureSearchLog,
#     UserPreferCategory,
# )
# from apps.lecture.services.recommendation_service.constants import (
#     ALS_TRAINING_LOCK_KEY,
#     MODEL_VERSION,
# )
# from apps.lecture.services.recommendation_service.data_loader import DataLoader, MatrixBundle
# from apps.lecture.services.recommendation_service.model_trainer import (
#     MODEL_BACKUP_PATH,
#     MODEL_BUNDLE_PATH,
#     ModelTrainer,
# )
# from apps.lecture.services.recommendation_service.recommender import RecommendationService
# from apps.studies.models.groups import GroupMember, StudyGroup, StudyLecture
#
# # 테스트용 사용자 모델 가져오기
# # Mypy는 여기서 얻은 User를 타입이 아닌 '변수'로 간주하여 오류 발생.
# User = get_user_model()
#
#
# class RecommendationIntegrationTest(IsolatedRedisTestClient):
#     """
#     ALS 추천 시스템의 모든 핵심 컴포넌트(DataLoader, Trainer, Service, API)를
#     통합적으로 검증하는 테스트 스위트.
#     """
#
#     # 클래스 변수 타입 힌트는 모두 Any를 사용합니다.
#     client: APIClient
#     user_a: Any
#     user_b: Any
#     cold_user: Any
#     no_data_user: Any
#     lectures: List[CrawledLecture]
#     cat_dev: Category
#     cat_design: Category
#     cold_user_bookmarked_lec: Any
#
#     @classmethod
#     def setUpTestData(cls) -> None:
#         """테스트 데이터 설정: 사용자, 강의, 카테고리, 상호작용 생성"""
#
#         cls.user_a = User.objects.create_user(
#             email="a@test.com",
#             password="password",
#             nickname="a_nick",
#             name="A",
#             phone_number="01011112222",
#             gender="M",
#             birthday="1990-01-01",
#             is_active=True,
#         )
#         cls.user_b = User.objects.create_user(
#             email="b@test.com",
#             password="password",
#             nickname="b_nick",
#             name="B",
#             phone_number="01033334444",
#             gender="F",
#             birthday="1991-01-01",
#             is_active=True,
#         )
#         cls.cold_user = User.objects.create_user(
#             email="c@test.com",
#             password="password",
#             nickname="c_nick",
#             name="C",
#             phone_number="01055556666",
#             gender="M",
#             birthday="1992-01-01",
#             is_active=True,
#         )
#         cls.no_data_user = User.objects.create_user(
#             email="d@test.com",
#             password="password",
#             nickname="d_nick",
#             name="D",
#             phone_number="01077778888",
#             gender="F",
#             birthday="1993-01-01",
#             is_active=True,
#         )
#
#         cls.cat_dev = Category.objects.create(name="개발")
#         cls.cat_design = Category.objects.create(name="디자인")
#
#         cls.lectures = [
#             CrawledLecture.objects.create(
#                 id=i,
#                 title=f"Lec {i}",
#                 instructor="Inst",
#                 average_rating=5.0 - (i / 10),
#                 original_price=10000 + i * 100,
#                 platform="INFLEARN" if i % 2 == 0 else "UDEMY",
#                 # 🛠️ 필수 필드 추가: duration, difficulty, description, url_link
#                 duration=60 + i * 10,  # NotNullViolation 해결 (SmallIntegerField)
#                 difficulty=CrawledLecture.DifficultyEnum.NORMAL,  # NotNullViolation 해결
#                 description="Test lecture description.",  # NotNullViolation 해결 (TextField)
#                 url_link=f"https://mock.com/course/lec{i}",  # NotNullViolation 해결 (CharField)
#                 # uuid는 UUIDBaseModel에 의해 자동으로 생성되지만, 명시적으로 제공해도 무방합니다.
#                 # uuid=str(uuid.uuid4())
#             )
#             for i in range(1, 11)
#         ]
#
#         LectureBookmark.objects.create(user=cls.user_a, lecture=cls.lectures[0])
#         LectureBookmark.objects.create(user=cls.user_b, lecture=cls.lectures[1])
#         UserPreferCategory.objects.create(user=cls.user_a, category=cls.cat_dev)
#         LectureSearchLog.objects.create(user=cls.user_a, keyword="Lec 4", created_at=timezone.now() - timedelta(days=1))
#
#         study = StudyGroup.objects.create(
#             name="Study 1", start_at=timezone.now(), end_at=timezone.now() + timedelta(days=7)
#         )
#         GroupMember.objects.create(user=cls.user_b, study_group=study)
#         StudyLecture.objects.create(study_group=study, lecture=cls.lectures[2])
#
#         cls.cold_user_bookmarked_lec = cls.lectures[4]
#         LectureBookmark.objects.create(user=cls.cold_user, lecture=cls.cold_user_bookmarked_lec)
#         UserPreferCategory.objects.create(user=cls.cold_user, category=cls.cat_design)
#
#         LectureCategory.objects.create(lecture=cls.lectures[0], category=cls.cat_dev)
#         LectureCategory.objects.create(lecture=cls.lectures[1], category=cls.cat_dev)
#         LectureCategory.objects.create(lecture=cls.lectures[2], category=cls.cat_design)
#         LectureCategory.objects.create(lecture=cls.lectures[3], category=cls.cat_design)
#         LectureCategory.objects.create(lecture=cls.lectures[4], category=cls.cat_design)
#
#     def setUp(self) -> None:
#         super().setUp()
#         self.client = APIClient()
#
#     def tearDown(self) -> None:
#         """테스트 후 캐시 및 모델 파일 정리"""
#         super().tearDown()
#         if os.path.exists(MODEL_BUNDLE_PATH):
#             os.remove(MODEL_BUNDLE_PATH)
#         if os.path.exists(MODEL_BACKUP_PATH):
#             os.remove(MODEL_BACKUP_PATH)
#         cache.delete(ALS_TRAINING_LOCK_KEY)
#
#     def _get_trainer(self) -> ModelTrainer:
#         """ModelTrainer 인스턴스 반환 헬퍼"""
#         return ModelTrainer(DataLoader())
#
#     def _get_service(self) -> RecommendationService:
#         """RecommendationService 인스턴스 반환 헬퍼"""
#         return RecommendationService()
#
#     # --------------------------------------------------------------------------
#     ## DataLoader & ModelTrainer Core Logic Tests
#     # --------------------------------------------------------------------------
#
#     def test_data_loader_interactions_and_matrix(self) -> None:
#         """DataLoader: 모든 상호작용 피처 통합 및 희소 행렬 구축 검증"""
#         loader: DataLoader = DataLoader()
#
#         matrix_bundle: MatrixBundle = loader.build_user_item_matrix()
#         self.assertIsNotNone(matrix_bundle, "행렬 번들은 None이 아니어야 합니다.")
#
#         matrix_coo, u_to_i, l_to_i, _, _ = cast(
#             Tuple[Any, Dict[int, int], Dict[int, int], List[int], List[int]], matrix_bundle
#         )
#
#         self.assertEqual(len(u_to_i), 3, "총 사용자 매핑 수는 3명이어야 합니다.")
#
#         # User A의 Lec 1 점수 검증 (Line 142 오류 해결)
#         # 지역 변수의 명시적 타입을 제거하고 cast 결과만 할당
#         user_a_casted = cast(Any, self.user_a)  # Line 142
#         matrix_csr: Any = matrix_coo.tocsr()
#         user_a_idx: int = u_to_i[user_a_casted.id]
#         lec_1_idx: int = l_to_i[self.lectures[0].id]
#         score_lec_1: float = matrix_csr[user_a_idx, lec_1_idx]
#         self.assertAlmostEqual(score_lec_1, 12.85, places=2, msg="Lec 1의 상호작용 점수가 정확해야 합니다.")
#
#         LectureSearchLog.objects.create(
#             user=user_a_casted, keyword="TestOld", created_at=timezone.now() - timedelta(days=90)
#         )
#
#     def test_model_trainer_safe_dump_and_recovery(self) -> None:
#         """ModelTrainer: 안전 저장 및 저장 실패 시 복구 로직 검증"""
#         trainer: ModelTrainer = self._get_trainer()
#
#         self.assertTrue(trainer.train_and_save_full_model(), "모델 학습 및 저장이 성공해야 합니다.")
#         self.assertFalse(os.path.exists(MODEL_BACKUP_PATH), "성공 후 백업 파일은 삭제되어야 합니다.")
#
#         if os.path.exists(MODEL_BUNDLE_PATH):
#             shutil.copyfile(MODEL_BUNDLE_PATH, MODEL_BACKUP_PATH)
#
#         if os.path.exists(MODEL_BUNDLE_PATH):
#             os.remove(MODEL_BUNDLE_PATH)
#
#         self.assertTrue(os.path.exists(MODEL_BACKUP_PATH), "롤백 테스트를 위해 백업 파일이 존재해야 합니다.")
#
#     def test_partial_fit_and_fallback(self) -> None:
#         """ModelTrainer: 점진적 학습 및 폴백 (신규 유저/아이템) 검증"""
#         trainer: ModelTrainer = self._get_trainer()
#
#         trainer.train_and_save_full_model()
#
#         # 새로운 상호작용 추가 (Line 173 오류 해결)
#         user_a_casted = cast(Any, self.user_a)  # Line 173
#         LectureBookmark.objects.create(
#             user=user_a_casted, lecture=self.lectures[5], created_at=timezone.now() + timedelta(minutes=1)
#         )
#
#         self.assertTrue(trainer.partial_fit_model_and_save(), "점진적 학습 및 저장이 성공해야 합니다.")
#
#         if os.path.exists(MODEL_BUNDLE_PATH):
#             os.remove(MODEL_BUNDLE_PATH)
#
#         # 신규 유저의 상호작용 추가 (Line 182 오류 해결)
#         new_user = cast(
#             Any,
#             User.objects.create_user(
#                 email="new@test.com",
#                 password="p",
#                 nickname="n_nick",
#                 name="N",
#                 phone_number="01099990000",
#                 gender="M",
#                 birthday="1995-01-01",
#                 is_active=True,  # 'username' 제거
#             ),
#         )
#         LectureBookmark.objects.create(user=new_user, lecture=self.lectures[6])
#
#         self.assertTrue(trainer.partial_fit_model_and_save(), "부분 학습 실패 후 전체 학습으로 폴백되어야 합니다.")
#
#         _, u_to_i, *_, _ = trainer.load_model_and_mappings()
#         self.assertIn(
#             new_user.id, cast(Dict[int, int], u_to_i), "Full Training으로 폴백 후 New User가 포함되어야 합니다."
#         )
#
#     # --------------------------------------------------------------------------
#     ## RecommendationService Core Logic Tests
#     # --------------------------------------------------------------------------
#
#     def test_service_cold_start_popular_fallback(self) -> None:
#         """RecommendationService: 상호작용 없는 사용자의 인기 강의 폴백 검증"""
#         self._get_trainer().train_and_save_full_model()
#         service: RecommendationService = self._get_service()
#
#         # No Data User (Line 200 오류 해결)
#         no_data_user_casted = cast(Any, self.no_data_user)  # Line 200
#         top_n: int = 3
#         recommendations_qs: QuerySet[CrawledLecture] = service.recommend_lectures(no_data_user_casted.id, top_n=top_n)
#         recommended_ids: List[int] = list(recommendations_qs.values_list("id", flat=True))
#
#         self.assertEqual(len(recommended_ids), top_n)
#         self.assertEqual(recommended_ids[0], self.lectures[0].id, "가장 평점 높은 강의가 첫 번째여야 합니다.")
#
#     def test_service_cold_start_category_fallback(self) -> None:
#         """RecommendationService: 선호 카테고리 기반 콜드 스타트 폴백 검증"""
#         self._get_trainer().train_and_save_full_model()
#         service: RecommendationService = self._get_service()
#
#         # Cold User (Line 214 오류 해결)
#         cold_user_casted = cast(Any, self.cold_user)  # Line 214
#         cold_user_id: int = cold_user_casted.id
#
#         if service._user_to_idx is not None:
#             service._user_to_idx = {uid: idx for uid, idx in service._user_to_idx.items() if uid != cold_user_id}
#
#         top_n: int = 2
#         recommendations_qs: QuerySet[CrawledLecture] = service.recommend_lectures(cold_user_id, top_n=top_n)
#         recommended_ids: List[int] = list(recommendations_qs.values_list("id", flat=True))
#
#         self.assertLessEqual(len(recommended_ids), top_n)
#
#     def test_service_als_recommendation_and_reranking(self) -> None:
#         """RecommendationService: ALS 예측 및 Reranking 검증"""
#         self._get_trainer().train_and_save_full_model()
#         service: RecommendationService = self._get_service()
#
#         # User A (Line 232 오류 해결)
#         user_a_casted = cast(Any, self.user_a)  # Line 232
#         recommendations_qs: QuerySet[CrawledLecture] = service.recommend_lectures(user_a_casted.id, top_n=5)
#         recommended_ids: List[int] = list(recommendations_qs.values_list("id", flat=True))
#
#         self.assertNotIn(self.lectures[0].id, recommended_ids, "Lec 1은 이미 북마크했으므로 추천되면 안 됩니다.")
#
#         self.assertIn(self.lectures[1].id, recommended_ids, "Lec 2(카테고리 매칭)는 추천 목록에 포함되어야 합니다.")
#
#     def test_service_metadata_cache_fallback(self) -> None:
#         """RecommendationService: 메타데이터 캐시 실패 시 DB 폴백 및 저장 검증 (커버리지)"""
#         self._get_trainer().train_and_save_full_model()
#         service: RecommendationService = self._get_service()
#         lec_id: int = self.lectures[0].id
#
#         cache.delete(f"lecture_metadata_{MODEL_VERSION}:{lec_id}")
#         rating, categories = service._get_lecture_metadata_cached(lec_id)
#
#         self.assertAlmostEqual(rating, 4.9, places=2, msg="메타데이터는 DB에서 정확하게 로드되어야 합니다.")
#
#     # --------------------------------------------------------------------------
#     ## API Integration & Optimization Tests
#     # --------------------------------------------------------------------------
#
#     def test_api_integration_and_n_plus_1_optimization(self) -> None:
#         """RecommendationView: API 호출, 권한 및 N+1 최적화 검증"""
#         self._get_trainer().train_and_save_full_model()
#
#         response: APIResponse = self.client.get(reverse("recommendations"))
#         self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
#
#         # 2. 인증된 사용자 (user_a 로그인) (Line 263 오류 해결)
#         user_a_casted = cast(Any, self.user_a)  # Line 263
#         self.client.force_login(user_a_casted)
#
#         with self.assertNumQueries(4):
#             response = self.client.get(reverse("recommendations"))
#
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#
#         data: List[Dict[str, Any]] = response.json()
#
#         # 3. is_bookmarked 최적화 결과 검증
#         for item in data:
#             if item["id"] == self.lectures[2].id:  # Lec 3
#                 self.assertFalse(item["is_bookmarked"], "Lec 3은 User A가 북마크하지 않았으므로 False여야 합니다.")
#                 # Category 정보가 프리패치되었는지 확인
#                 self.assertIn(
#                     "디자인",
#                     cast(List[Dict[str, Any]], item["categories"])[0]["name"],
#                     "카테고리 정보가 올바르게 프리패치되어야 합니다.",
#                 )
#                 break
