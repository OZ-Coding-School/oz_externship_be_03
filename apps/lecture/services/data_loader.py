from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import numpy as np
from django.db.models import Case, FloatField, Q, Sum, Value, When
from scipy.sparse import coo_matrix

from apps.lecture.models import (
    CrawledLecture,
    CrawledLectureReview,
    LectureBookmark,
    LectureCategory,
    LectureSearchLog,
    UserPreferCategory,
)
from apps.studies.models.groups import StudyLecture


class DataLoader:
    """
    Django ORM 데이터를 로드하고 전처리하여 ALS 학습을 위한 희소 행렬을 생성.
    모든 사용자 상호작용을 통합 쿼리 및 Python 후처리로 최적화하여 로드.
    """

    def __init__(self, weights: Dict[str, float], rating_map: Dict[str, float]) -> None:
        """DataLoader 인스턴스 초기화. 가중치, 평점 맵을 주입받음."""
        self.WEIGHTS = weights
        self.RATING_SCORE_MAP = rating_map
        # 강의-카테고리 맵을 지연 로딩하기 위해 None으로 초기화
        self._lecture_category_map: Optional[Dict[int, set[int]]] = None

    def _load_lecture_category_map(self) -> Dict[int, set[int]]:
        """모든 강의-카테고리 관계를 DB에서 로드하여 반환 (N+1 방지)."""
        lecture_category_map: Dict[int, set[int]] = {}
        # values_list를 사용하여 불필요한 모델 인스턴스 생성 피함.
        for lec_id, cat_id in LectureCategory.objects.values_list("lecture_id", "category_id"):
            lecture_category_map.setdefault(lec_id, set()).add(cat_id)
        return lecture_category_map

    def get_lecture_category_map(self) -> Dict[int, set[int]]:
        """캐시된 강의-카테고리 관계 맵 반환, 없으면 로드 후 캐싱."""
        if self._lecture_category_map is None:
            self._lecture_category_map = self._load_lecture_category_map()
        return self._lecture_category_map

    def _get_all_interactions(self, users: List[int]) -> Dict[Tuple[int, int], float]:
        """
        전체 사용자 및 강의에 대한 상호작용 점수를 DB 쿼리 최적화하여 한 번에 집계.
        """
        all_interactions: defaultdict[Tuple[int, int], float] = defaultdict(float)

        # 1. 북마크 점수 누적
        bookmarks = LectureBookmark.objects.filter(user_id__in=users).values_list("user_id", "lecture_id")
        for user_id, lec_id in bookmarks:
            all_interactions[(user_id, lec_id)] += self.WEIGHTS["bookmark"]

        # 2. 스터디 참여 점수 누적
        try:
            study_participations = (
                StudyLecture.objects.filter(study_group_id__group_members__user_id__in=users)
                .values_list("study_group_id__group_members__user_id", "lecture_id")
                .distinct()
            )

            for user_id, lec_id in study_participations:
                all_interactions[(user_id, lec_id)] += self.WEIGHTS["study_participation"]
        except Exception:
            pass

        # 3. 사용자 선호 카테고리 매칭 점수 누적
        user_prefer_map: defaultdict[int, set[int]] = defaultdict(set)
        for user_id, cat_id in UserPreferCategory.objects.filter(user_id__in=users).values_list(
            "user_id", "category_id"
        ):
            user_prefer_map[user_id].add(cat_id)

        lecture_category_map = self.get_lecture_category_map()

        for user_id, lec_id in all_interactions.keys():
            user_prefs = user_prefer_map[user_id]
            lec_cats = lecture_category_map.get(lec_id, set())
            matched_cats = user_prefs.intersection(lec_cats)
            if matched_cats:
                all_interactions[(user_id, lec_id)] += len(matched_cats) * self.WEIGHTS["category_match"]

        # 4. 리뷰 평점 점수 반영 (Django ORM 집계)
        rating_cases = [
            When(rating=k, then=Value(v, output_field=FloatField())) for k, v in self.RATING_SCORE_MAP.items()
        ]

        # ORM 레벨에서 평점 평균을 계산하여 DB I/O 최적화
        lecture_avg_ratings = (
            CrawledLectureReview.objects.values("lecture_id")
            .annotate(score=Case(*rating_cases, default=Value(0.0, output_field=FloatField())))
            .values("lecture_id")
            .annotate(avg_rating=Sum("score") / Sum(Value(1)))
            .values("lecture_id", "avg_rating")
        )

        avg_rating_map = {r["lecture_id"]: r["avg_rating"] for r in lecture_avg_ratings}
        weighted_rating = self.WEIGHTS["review_rating"]

        for (user_id, lec_id), score in all_interactions.items():
            if lec_id in avg_rating_map:
                all_interactions[(user_id, lec_id)] += avg_rating_map[lec_id] * weighted_rating

        # 5. 검색어 기반 점수 누적
        user_keywords: defaultdict[int, List[str]] = defaultdict(list)
        for user_id, keyword in LectureSearchLog.objects.filter(user_id__in=users).values_list("user_id", "keyword"):
            if keyword and keyword not in user_keywords[user_id]:
                user_keywords[user_id].append(keyword)

        weighted_search = self.WEIGHTS["search"]

        for user_id, keywords in user_keywords.items():
            if not keywords:
                continue

            search_query = Q()
            for keyword in keywords:
                # 강의 제목에 키워드가 포함되는지 검사
                search_query |= Q(title__icontains=keyword)

            # 단일 쿼리로 해당 유저의 모든 매칭 강의 ID 조회
            matched_lectures = CrawledLecture.objects.filter(search_query).values_list("id", flat=True)

            # 매칭된 강의에 대해 단순 가중치 부여
            for lec_id in matched_lectures:
                all_interactions[(user_id, lec_id)] += weighted_search

        return all_interactions

    def build_user_item_matrix(self, target_user_ids: Optional[List[int]] = None) -> Tuple[
        Optional[coo_matrix],
        Optional[Dict[int, int]],
        Optional[Dict[int, int]],
        Optional[List[int]],
        Optional[List[int]],
    ]:
        """ALS 학습에 필요한 사용자-강의 상호작용 희소 행렬과 인덱스 맵 생성."""
        interaction_rows: List[int] = []
        interaction_cols: List[int] = []
        interaction_data: List[float] = []

        # 상호작용 데이터가 있는 모든 사용자/강의 목록 추출
        users = target_user_ids or list(LectureBookmark.objects.values_list("user_id", flat=True).distinct())
        lectures = list(CrawledLecture.objects.filter(bookmarks__isnull=False).values_list("id", flat=True).distinct())

        if not users or not lectures:
            return None, None, None, None, None

        all_interactions = self._get_all_interactions(users)

        # 고유 ID를 0부터 시작하는 행렬 인덱스로 매핑
        user_idx_map: Dict[int, int] = {user: i for i, user in enumerate(users)}
        lecture_idx_map: Dict[int, int] = {lec: i for i, lec in enumerate(lectures)}

        # 집계된 점수를 희소 행렬의 (행, 열, 값) 데이터로 변환
        for (user_id, lec_id), score in all_interactions.items():
            if user_id in user_idx_map and lec_id in lecture_idx_map:
                interaction_rows.append(user_idx_map[user_id])
                interaction_cols.append(lecture_idx_map[lec_id])
                interaction_data.append(float(score))

        if not interaction_data:
            return None, None, None, None, None

        # coo_matrix 생성
        user_item_matrix = coo_matrix(
            (np.array(interaction_data), (np.array(interaction_rows), np.array(interaction_cols))),
            shape=(len(users), len(lectures)),
        )

        return user_item_matrix, user_idx_map, lecture_idx_map, users, lectures
