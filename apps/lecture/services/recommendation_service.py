from typing import Dict, List, Optional, Tuple

import implicit  # type: ignore  # Implicit ALS 구현 라이브러리 (타입 스텁 미제공)
import numpy as np  # 수치 계산 및 배열 처리용 (행렬 변환에 필수)
from django.contrib.auth import get_user_model
from django.db.models import QuerySet
from scipy.sparse import coo_matrix  # 좌표 형식(Coordinate format)의 희소 행렬 처리용

from apps.lecture.models import (
    CrawledLecture,
    CrawledLectureReview,
    LectureBookmark,
    LectureCategory,
    LectureSearchLog,
    UserPreferCategory,
)
from apps.studies.models.groups import StudyLecture

User = get_user_model()

RATING_SCORE_MAP: Dict[str, float] = {
    # 문자열 평점 필드를 수치형 점수 (float)로 매핑하기 위한 딕셔너리
    "5_OUT_OF_5_STARS": 5.0,
    "4_OUT_OF_5_STARS": 4.0,
    "3_OUT_OF_5_STARS": 3.0,
    "2_OUT_OF_5_STARS": 2.0,
    "1_OUT_OF_5_STARS": 1.0,
}


class RecommendationService:
    WEIGHTS: Dict[str, float] = {
        # 사용자 행동별 가중치 설정: Implicit ALS의 신뢰도(Confidence) 점수에 기여
        "bookmark": 3.0,  # 북마크: 가장 강력한 긍정 신호
        "search": 1.0,  # 검색: 낮은 수준의 관심사 표현
        "study_participation": 2.0,  # 스터디 참여: 높은 몰입도 신호
        "category_match": 2.5,  # 카테고리 일치: 장기 선호도 반영
        "review_rating": 1.5,  # 리뷰 평점: 콘텐츠 품질 만족도 반영
    }

    def __init__(self) -> None:
        """
        RecommendationService 인스턴스 초기화 시,
        반복 조회되는 LectureCategory 맵핑 데이터를 한 번만 로드하여 캐시. (쿼리 최적화)
        """
        self._lecture_category_map = self._load_lecture_category_map()

    def _load_lecture_category_map(self) -> Dict[int, set[int]]:
        """
        모든 강의-카테고리 맵핑 데이터를 DB에서 로드하여 반환.
        N+1 쿼리 방지 및 반복적인 DB 조회를 회피.
        """
        lecture_category_map: Dict[int, set[int]] = {}
        # values_list를 사용하여 불필요한 모델 인스턴스 생성 피함.
        for lec_id, cat_id in LectureCategory.objects.values_list("lecture_id", "category_id"):
            lecture_category_map.setdefault(lec_id, set()).add(cat_id)
        return lecture_category_map

    def aggregate_user_interactions(self, user_id: int) -> Dict[int, float]:
        """
        다중 암묵적 행동 신호를 통합하여 강의별 가중치 점수(Confidence Score) 생성

        :param user_id: 사용자 고유 ID
        :return: {강의ID: 총 가중치 점수} 딕셔너리
        """
        score_map: Dict[int, float] = {}

        # 1. 북마크 점수 누적: 사용자 의도가 가장 명확
        bookmarks = LectureBookmark.objects.filter(user_id=user_id).values_list("lecture_id", flat=True)
        for lec_id in bookmarks:
            score_map[lec_id] = score_map.get(lec_id, 0.0) + self.WEIGHTS["bookmark"]

        # 2. 검색어 기반 점수 누적: 관심사 파악
        search_keywords = LectureSearchLog.objects.filter(user_id=user_id).values_list("keyword", flat=True)
        for keyword in search_keywords:
            # 검색어와 강의 제목의 부분 일치 강의를 찾아 점수 부여
            matched_lectures = CrawledLecture.objects.filter(title__icontains=keyword).values_list("id", flat=True)
            for lec_id in matched_lectures:
                score_map[lec_id] = score_map.get(lec_id, 0.0) + self.WEIGHTS["search"]

        # 3. 스터디 참여 점수 누적: 높은 몰입도 신호
        try:
            # 사용자가 속한 스터디 그룹의 강의 조회
            study_lecture_ids = StudyLecture.objects.filter(study_group_id__group_members__user_id=user_id).values_list(
                "lecture_id", flat=True
            )
            for lec_id in study_lecture_ids:
                score_map[lec_id] = score_map.get(lec_id, 0.0) + self.WEIGHTS["study_participation"]
        except Exception:
            # 관련 모델 또는 데이터 구조 변경 시 에러 무시
            pass

        # 4. 사용자 선호 카테고리 반영 (캐시된 맵 _lecture_category_map 사용): 장기적 선호도 반영
        prefer_category_ids = set(
            UserPreferCategory.objects.filter(user_id=user_id).values_list("category_id", flat=True)
        )
        lecture_category_map = self._lecture_category_map

        for lec_id in list(score_map.keys()):
            lec_cats = lecture_category_map.get(lec_id, set())
            matched_cats = lec_cats.intersection(prefer_category_ids)
            # 일치하는 카테고리 수에 비례하여 가중치 부여
            if matched_cats:
                score_map[lec_id] += len(matched_cats) * self.WEIGHTS["category_match"]

        # 5. 리뷰 평점 점수 반영: 콘텐츠 품질 만족도 반영
        review_map: Dict[int, List[float]] = {}
        # 상호작용이 있는 강의의 리뷰만 필터링하여 리뷰 데이터셋 크기 감소
        reviews = CrawledLectureReview.objects.filter(lecture__in=score_map.keys())
        for r in reviews:
            review_map.setdefault(r.lecture_id, []).append(RATING_SCORE_MAP.get(r.rating, 0.0))

        for lec_id, ratings in review_map.items():
            avg_rating = sum(ratings) / len(ratings) if ratings else 0.0
            # 평균 평점에 가중치를 곱하여 최종 신뢰도 점수에 합산
            score_map[lec_id] = score_map.get(lec_id, 0.0) + avg_rating * self.WEIGHTS["review_rating"]

        return score_map

    def build_user_item_matrix(
        self,
    ) -> Tuple[
        Optional[coo_matrix],
        Optional[Dict[int, int]],
        Optional[Dict[int, int]],
        Optional[List[int]],
        Optional[List[int]],
    ]:
        """
        ALS 훈련을 위한 사용자-아이템 희소 행렬 구축
        원본 ID와 행렬 인덱스 간의 맵핑 정보 반환.

        :return: (희소 행렬, 사용자 인덱스 맵, 강의 인덱스 맵, 사용자 ID 리스트, 강의 ID 리스트)
        """
        interaction_rows: List[int] = []
        interaction_cols: List[int] = []
        interaction_data: List[float] = []

        # 상호작용 데이터(북마크)가 있는 사용자 및 강의만 추출 (차원 축소 목적)
        users = list(User.objects.filter(lecture_bookmarks__isnull=False).values_list("id", flat=True).distinct())
        lectures = list(CrawledLecture.objects.filter(bookmarks__isnull=False).values_list("id", flat=True).distinct())

        # 고유 ID를 0부터 시작하는 행렬 인덱스로 매핑
        user_idx_map: Dict[int, int] = {user: i for i, user in enumerate(users)}
        lecture_idx_map: Dict[int, int] = {lec: i for i, lec in enumerate(lectures)}

        if not users or not lectures:
            return None, None, None, None, None

        # 유저별 집계 점수를 희소 행렬의 (행, 열, 값) 데이터로 변환
        for user_id in users:
            score_map = self.aggregate_user_interactions(user_id)
            for lec_id, score in score_map.items():
                if lec_id in lecture_idx_map:
                    interaction_rows.append(user_idx_map[user_id])
                    interaction_cols.append(lecture_idx_map[lec_id])
                    interaction_data.append(float(score))

        if not interaction_data:
            return None, None, None, None, None

        # coo_matrix 생성: mypy 오류 해결을 위해 모든 입력 리스트를 np.array로 변환
        user_item_matrix = coo_matrix(
            (np.array(interaction_data), (np.array(interaction_rows), np.array(interaction_cols))),
            shape=(len(users), len(lectures)),
        )

        return user_item_matrix, user_idx_map, lecture_idx_map, users, lectures

    def train_als_model(
        self,
    ) -> Tuple[
        Optional[coo_matrix],
        Optional[implicit.als.AlternatingLeastSquares],
        Optional[Dict[int, int]],
        Optional[Dict[int, int]],
        Optional[List[int]],
        Optional[List[int]],
    ]:
        """
        Implicit ALS 모델 학습 실행. 훈련에 사용된 행렬 객체를 함께 반환.
        (행렬 객체 반환은 build_user_item_matrix()의 중복 호출을 막기 위함)

        :return: (행렬 객체, 학습 완료 모델, 사용자 인덱스 맵, 강의 인덱스 맵, 사용자 ID 리스트, 강의 ID 리스트)
        """
        matrix, u_to_i, l_to_i, users, lectures = self.build_user_item_matrix()
        if matrix is None:
            return None, None, None, None, None, None

        model = implicit.als.AlternatingLeastSquares(
            factors=50,
            regularization=0.1,
            iterations=15,
            calculate_training_loss=False,
            use_gpu=False,
        )
        # 모델 훈련: Item x User 행렬 (matrix.T)을 CSR 형식으로 변환하여 효율적으로 훈련
        model.fit(matrix.T.tocsr())

        return matrix, model, u_to_i, l_to_i, users, lectures

    def recommend_lectures_for_user(self, user_id: int, top_n: int = 5) -> Optional[QuerySet[CrawledLecture]]:
        """
        특정 사용자 대상 ALS 모델을 사용해 Top-N 강의 추천 결과를 QuerySet으로 반환

        :param user_id: 추천 대상 사용자 ID
        :param top_n: 반환할 추천 강의 수
        :return: 추천 강의 QuerySet 또는 폴백 QuerySet
        """
        # 1. 모델 훈련 및 맵핑 정보 로드
        matrix, model, user_to_idx, lecture_to_idx, _, _ = self.train_als_model()

        # 2. 모델 실패/콜드 스타트 폴백 처리
        if (
            model is None
            or user_to_idx is None
            or lecture_to_idx is None
            or user_id not in user_to_idx
            or matrix is None
        ):
            # 훈련 데이터 부족, 모델 로드 실패, 또는 신규 사용자(콜드 스타트)인 경우
            # 인기순 (average_rating 기준)으로 폴백 처리
            return CrawledLecture.objects.order_by("-average_rating")[:top_n]

        # 3. 추천 계산
        user_index = user_to_idx[user_id]

        recommended = model.recommend(
            user_index,
            matrix.tocsr(),  # 훈련에 사용된 행렬 객체 재활용
            N=top_n,
            filter_already_liked_items=True,  # 이미 상호작용한 항목 제외
        )

        # 4. 결과 변환 및 QuerySet 반환
        idx_to_lecture_id = {v: k for k, v in lecture_to_idx.items()}
        recommended_ids = [idx_to_lecture_id[idx] for idx, _ in recommended]

        lectures = CrawledLecture.objects.filter(id__in=recommended_ids).prefetch_related(
            "lecture_categories__category"
        )
        return lectures
