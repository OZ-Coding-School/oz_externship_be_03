from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import implicit  # type: ignore  # Implicit ALS 구현 라이브러리 (타입 스텁 미제공)
import numpy as np  # 수치 계산 및 배열 처리용 (행렬 변환에 필수)
from django.contrib.auth import get_user_model
from django.db.models import Q, QuerySet
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

# 문자열 평점을 숫자로 매핑하는 딕셔너리
RATING_SCORE_MAP: Dict[str, float] = {
    "5_OUT_OF_5_STARS": 5.0,
    "4_OUT_OF_5_STARS": 4.0,
    "3_OUT_OF_5_STARS": 3.0,
    "2_OUT_OF_5_STARS": 2.0,
    "1_OUT_OF_5_STARS": 1.0,
}


class RecommendationService:
    # 사용자 행동별 가중치를 설정하는 딕셔너리
    WEIGHTS: Dict[str, float] = {
        "bookmark": 3.0,  # 북마크: 가장 강한 긍정 신호
        "search": 1.0,  # 검색: 낮은 강도의 관심 표현
        "study_participation": 2.0,  # 스터디 참여: 높은 몰입 신호
        "category_match": 2.5,  # 카테고리 일치: 장기 선호도 반영
        "review_rating": 1.5,  # 리뷰 평점: 품질 만족도 반영
    }

    def __init__(self) -> None:
        """
        RecommendationService 인스턴스 초기화.
        DB 쿼리를 지연시키기 위해 맵핑 데이터를 None으로 초기화 (Lazy Loading 준비).
        """
        self._lecture_category_map: Optional[Dict[int, set[int]]] = None

    def _load_lecture_category_map(self) -> Dict[int, set[int]]:
        """
        모든 강의-카테고리 관계를 DB에서 로드하여 반환.
        N+1 쿼리 방지 및 반복적인 DB 조회를 회피.
        """
        lecture_category_map: Dict[int, set[int]] = {}
        # values_list를 사용하여 불필요한 모델 인스턴스 생성 피함.
        for lec_id, cat_id in LectureCategory.objects.values_list("lecture_id", "category_id"):
            lecture_category_map.setdefault(lec_id, set()).add(cat_id)
        return lecture_category_map

    def get_lecture_category_map(self) -> Dict[int, set[int]]:
        """
        캐시된 강의-카테고리 관계를 반환. 없으면 _load_lecture_category_map() 호출 후 캐싱.
        """
        if self._lecture_category_map is None:
            self._lecture_category_map = self._load_lecture_category_map()
        return self._lecture_category_map

    def aggregate_user_interactions(self, user_id: int) -> Dict[int, float]:
        """
        사용자 행동 신호를 통합해 강의별 신뢰도 점수를 계산. (Pythonic 및 N+1 최적화 적용)

        :param user_id: 사용자 ID
        :return: {강의ID: 점수} 딕셔너리
        """
        # score_map을 defaultdict로 초기화하여 누적 시 .get(..., 0.0) 호출 생략
        score_map: defaultdict[int, float] = defaultdict(float)

        # 1. 북마크 점수 누적: 사용자 의도가 가장 명확
        bookmarks = LectureBookmark.objects.filter(user_id=user_id).values_list("lecture_id", flat=True)
        for lec_id in bookmarks:
            score_map[lec_id] += self.WEIGHTS["bookmark"]

        # 2. 검색어 기반 점수 누적: N+1 문제 예방을 위해 Q 객체로 통합 조회
        search_keywords = list(LectureSearchLog.objects.filter(user_id=user_id).values_list("keyword", flat=True))
        if search_keywords:
            query = Q()
            for keyword in search_keywords:
                # 모든 키워드를 Q 객체로 묶어 OR 조건으로 결합
                query |= Q(title__icontains=keyword)
            # 단 한 번의 쿼리로 모든 관련 강의 ID 조회
            matched_lectures = CrawledLecture.objects.filter(query).values_list("id", flat=True)
            for lec_id in matched_lectures:
                score_map[lec_id] += self.WEIGHTS["search"]

        # 3. 스터디 참여 점수 누적: 높은 몰입도 신호
        try:
            # 사용자가 속한 스터디 그룹의 강의 조회
            study_lecture_ids = StudyLecture.objects.filter(study_group_id__group_members__user_id=user_id).values_list(
                "lecture_id", flat=True
            )
            for lec_id in study_lecture_ids:
                score_map[lec_id] += self.WEIGHTS["study_participation"]
        except Exception:
            pass  # 데이터 구조 변경 시 안전하게 무시

        # 4. 사용자 선호 카테고리와 강의 카테고리 매칭에 따른 가중치 부여
        prefer_category_ids = set(
            UserPreferCategory.objects.filter(user_id=user_id).values_list("category_id", flat=True)
        )
        lecture_category_map = self.get_lecture_category_map()

        # score_map.keys() 이터레이터를 사용하여 메모리 효율적으로 반복
        for lec_id in score_map.keys():
            lec_cats = lecture_category_map.get(lec_id, set())
            matched_cats = lec_cats.intersection(prefer_category_ids)
            # 일치하는 카테고리 수에 비례하여 가중치 부여
            if matched_cats:
                score_map[lec_id] += len(matched_cats) * self.WEIGHTS["category_match"]

        # 5. 리뷰 평점 점수 반영: 콘텐츠 품질 만족도 반영 (I/O 및 Python 연산 최적화)
        review_map = defaultdict(list)

        # 필요한 필드('lecture_id', 'rating')만 가져와 DB-Python 간 전송량 감소
        reviews = CrawledLectureReview.objects.filter(lecture__in=score_map.keys()).values("lecture_id", "rating")

        for r in reviews:
            # defaultdict(list)로 setdefault 없이 바로 append 가능
            review_map[r["lecture_id"]].append(RATING_SCORE_MAP.get(r["rating"], 0.0))

        for lec_id, ratings in review_map.items():
            avg_rating = sum(ratings) / len(ratings) if ratings else 0.0
            # 평균 평점에 가중치를 곱하여 최종 신뢰도 점수에 합산
            score_map[lec_id] += avg_rating * self.WEIGHTS["review_rating"]

        # 최종적으로 defaultdict를 일반 dict으로 변환하여 반환 (타입 힌트 준수)
        return dict(score_map)

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
        ALS 학습에 필요한 사용자-강의 상호작용 희소 행렬과 인덱스 맵 생성

        :return: (희소 행렬, 사용자ID->행 인덱스, 강의ID->열 인덱스, 사용자 리스트, 강의 리스트)
        """
        interaction_rows: List[int] = []
        interaction_cols: List[int] = []
        interaction_data: List[float] = []

        # 북마크 테이블을 직접 조회하여 사용자 목록 추출 (User 테이블 JOIN 회피)
        users = list(LectureBookmark.objects.values_list("user_id", flat=True).distinct())
        # 상호작용 데이터(북마크)가 있는 강의만 필터링
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
        ALS 모델 훈련 실행 및 결과 반환

        :return: (훈련 행렬, ALS 모델, 사용자 인덱스 맵, 강의 인덱스 맵, 사용자 리스트, 강의 리스트)
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
        특정 사용자 대상 Top-N 맞춤 강의 추천 반환

        :param user_id: 사용자 ID
        :param top_n: 추천 개수
        :return: 추천 강의 QuerySet 또는 인기순 폴백 QuerySet
        """
        matrix, model, user_to_idx, lecture_to_idx, _, _ = self.train_als_model()

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
        recommended_ids = [idx_to_lecture_id[item[0]] for item in recommended if item[0] in idx_to_lecture_id]

        if not recommended_ids:
            # 추천 결괏값 없으면 인기순 폴백
            return CrawledLecture.objects.order_by("-average_rating")[:top_n]

        lectures = CrawledLecture.objects.filter(id__in=recommended_ids).prefetch_related(
            "lecture_categories__category"
        )
        return lectures
