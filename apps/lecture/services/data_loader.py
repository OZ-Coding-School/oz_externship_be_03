import logging
import pickle
from collections import defaultdict
from datetime import datetime, timedelta
from typing import (
    DefaultDict,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Union,
    cast,
)

import numpy as np
from django.core.cache import cache
from django.db import OperationalError, ProgrammingError
from django.db.models import Q
from django.utils import timezone
from scipy.sparse import coo_matrix

from apps.lecture.models import (
    CrawledLecture,
    LectureBookmark,
    LectureCategory,
    LectureSearchLog,
    UserPreferCategory,
)
from apps.lecture.services.constants import (
    HALF_LIFE_DAYS,
    ITEM_FEATURE_WEIGHTS,
    LECTURE_CATEGORY_MAP_CACHE_KEY,
    LECTURE_CATEGORY_MAP_TIMEOUT,
    SEARCH_LOG_DAYS_LIMIT,
    USER_INTERACTION_WEIGHTS,
)
from apps.studies.models.groups import GroupMember, StudyLecture

logger = logging.getLogger(__name__)

# 타입 힌팅 정의
# None을 포함하는 Optional 타입으로 정의
MatrixBundle = Optional[
    Tuple[
        coo_matrix,  # 상호작용 희소 행렬
        Dict[int, int],  # 사용자 ID -> 인덱스 매핑
        Dict[int, int],  # 강의 ID -> 인덱스 매핑
        List[int],  # 모든 사용자 ID 리스트
        List[int],  # 모든 강의 ID 리스트
    ]
]


class DataLoader:
    """ALS 학습을 위한 상호작용 데이터 로드 및 전처리 관리 클래스"""

    def __init__(self) -> None:
        """
        DataLoader 초기화: 상호작용 가중치 및 현재 시각 설정
        """
        # 사용자 상호작용 가중치
        self.user_weights: Dict[str, float] = USER_INTERACTION_WEIGHTS
        # 아이템 피처 가중치
        self.item_weights: Dict[str, float] = ITEM_FEATURE_WEIGHTS
        # 강의-카테고리 매핑 캐시 (메모리 캐시)
        self._lecture_category_map: Optional[Dict[int, Set[int]]] = None
        # 데이터 로드 및 감쇠 함수의 기준 시각 (훈련 시작 시점)
        self._now: datetime = timezone.now()

    # -- 1. 유틸리티 함수 (Utility Functions)

    def _get_decay_factor(self, created_at: datetime) -> float:
        """
        시간 기반 감쇠 계수 계산.
        최신 상호작용에 높은 가중치 부여,
        HALF_LIFE_DAYS를 기준으로 시간이 지날수록 점수가 0.5배씩 감소.

        :param created_at: 상호작용 발생 시각 (datetime)
        :return: 감쇠 계수 (float, 0.0 ~ 1.0)
        """
        time_diff: timedelta = self._now - created_at
        # 경과 일수 계산
        days_since: float = time_diff.total_seconds() / (60 * 60 * 24)
        # 감쇠 공식: 0.5 ** (경과 일수 / 반감기)
        return float(0.5 ** (days_since / HALF_LIFE_DAYS))

    @staticmethod
    def _load_lecture_category_map() -> Dict[int, Set[int]]:
        """
        데이터베이스에서 강의-카테고리 매핑을 직접 로드.

        :return: {강의 ID: {카테고리 ID}, ...} 형태의 딕셔너리
        """
        lecture_category_map: DefaultDict[int, Set[int]] = defaultdict(set)
        # LectureCategory 모델에서 (강의 ID, 카테고리 ID) 쌍을 조회하여 매핑 구축
        values_list: List[Tuple[int, int]] = list(LectureCategory.objects.values_list("lecture_id", "category_id"))
        for lec_id, cat_id in values_list:
            lecture_category_map[lec_id].add(cat_id)
        return dict(lecture_category_map)

    def get_lecture_category_map(self) -> Dict[int, Set[int]]:
        """
        강의-카테고리 매핑을 캐시에서 로드하거나, DB에서 로드 후 캐시.
        메모리(_lecture_category_map) -> Redis 캐시 -> DB 순서로 로드 시도.

        :return: {강의 ID: {카테고리 ID}, ...} 딕셔너리
        """
        if self._lecture_category_map is not None:
            return self._lecture_category_map

        # 1. Redis 캐시 로드 시도
        cached_data: Union[bytes, None] = cache.get(LECTURE_CATEGORY_MAP_CACHE_KEY)
        if cached_data is not None:
            try:
                # 바이트 데이터를 딕셔너리로 역직렬화 및 타입 캐스팅
                result: Dict[int, Set[int]] = cast(Dict[int, Set[int]], pickle.loads(cached_data))
                self._lecture_category_map = result
                return result
            except Exception as e:
                # 캐시 데이터 손상 시 경고 로깅 및 캐시 삭제
                logger.warning(f"[CACHE] Lecture category map cache corrupted. Reloading. Error: {e}")
                cache.delete(LECTURE_CATEGORY_MAP_CACHE_KEY)

        # 2. DB 로드
        lecture_category_map: Dict[int, Set[int]] = DataLoader._load_lecture_category_map()

        # 3. Redis 캐시 저장 시도
        try:
            # 새로 로드한 데이터를 직렬화하여 캐시에 저장 (TTL 적용)
            cache.set(
                LECTURE_CATEGORY_MAP_CACHE_KEY,
                pickle.dumps(lecture_category_map),
                LECTURE_CATEGORY_MAP_TIMEOUT,
            )
        except Exception as e:
            logger.error(f"[CACHE_FAIL] Error caching lecture category map: {e}")

        # 메모리 캐시 업데이트 및 반환
        self._lecture_category_map = lecture_category_map
        return lecture_category_map

    # -- 2. 상호작용 로드 함수 (Interaction Loading)

    def _load_user_interactions(
        self,
        users: List[int],
        last_trained_at: Optional[datetime],
    ) -> Dict[Tuple[int, int], float]:
        """
        북마크 및 스터디 참여 기반의 상호작용 점수 계산 및 로드.
        점진 학습 (last_trained_at) 및 감쇠 함수 적용.

        :param users: 대상 사용자 ID 리스트
        :param last_trained_at: 이전 학습 시점 (점진 학습 필터)
        :return: {(user_id, lecture_id): score} 딕셔너리
        """
        interactions: DefaultDict[Tuple[int, int], float] = defaultdict(float)
        weighted_bookmark: float = self.user_weights.get("bookmark", 0.0)
        weighted_study: float = self.user_weights.get("study_participation", 0.0)

        # 쿼리 필터: 대상 유저 + 점진 학습 시점 필터링
        query_filter: Q = Q(user_id__in=users)
        if last_trained_at:
            query_filter &= Q(created_at__gt=last_trained_at)

        # 1. 북마크 데이터 로드 (감쇠 미적용)
        if weighted_bookmark > 0:
            bookmarks: List[Tuple[int, int]] = list(
                LectureBookmark.objects.filter(query_filter).values_list("user_id", "lecture_id")
            )
            for user_id, lec_id in bookmarks:
                interactions[(user_id, lec_id)] += weighted_bookmark

        # 2. 스터디 참여 데이터 로드 (감쇠 적용)
        if weighted_study > 0:
            try:
                # GroupMember 필터링 (last_trained_at 이후 생성된 멤버)
                member_filter: Q = Q(user_id__in=users)
                if last_trained_at:
                    member_filter &= Q(created_at__gt=last_trained_at)

                study_group_ids: List[int] = list(
                    GroupMember.objects.filter(member_filter).values_list("study_group_id", flat=True).distinct()
                )

                if study_group_ids:
                    # StudyLecture 필터링 (last_trained_at 이후 추가된 강의)
                    lecture_filter: Q = Q(study_group_id__in=study_group_ids)
                    if last_trained_at:
                        lecture_filter &= Q(created_at__gt=last_trained_at)

                    study_participations: List[Tuple[int, int, datetime]] = list(
                        StudyLecture.objects.filter(lecture_filter).values_list(
                            "study_group_id", "lecture_id", "created_at"
                        )
                    )

                    # 그룹-유저 매핑
                    group_user_map: DefaultDict[int, Set[int]] = defaultdict(set)
                    group_members_data: List[Tuple[int, int]] = list(
                        GroupMember.objects.filter(study_group_id__in=study_group_ids, user_id__in=users).values_list(
                            "study_group_id", "user_id"
                        )
                    )

                    for grp_id, user_id in group_members_data:
                        group_user_map[grp_id].add(user_id)

                    # 점수 부여 및 감쇠 적용
                    for grp_id, lec_id, created_at in study_participations:
                        decay_factor: float = self._get_decay_factor(created_at)
                        decayed_score: float = weighted_study * decay_factor

                        for user_id in group_user_map.get(grp_id, set()):
                            interactions[(user_id, lec_id)] += decayed_score

            except (ProgrammingError, OperationalError) as e:
                logger.error(f"[DB] Error loading study participation data: {e}", exc_info=True)

        return dict(interactions)

    def _load_item_features(
        self,
        all_interactions: Dict[Tuple[int, int], float],
        last_trained_at: Optional[datetime],
    ) -> Dict[Tuple[int, int], float]:
        """
        사용자 선호 카테고리 일치 및 강의 평점 기반 아이템 피처 점수 계산.
        (last_trained_at은 현재 사용되지 않으나 인터페이스 통일성 유지)

        :param all_interactions: 현재까지 로드된 모든 상호작용 키 (u, l)
        :param last_trained_at: 이전 학습 시점 (currently unused)
        :return: {(user_id, lecture_id): feature_score} 딕셔너리
        """
        scores: DefaultDict[Tuple[int, int], float] = defaultdict(float)
        keys: Set[Tuple[int, int]] = set(all_interactions.keys())
        lec_ids: Set[int] = {lec for (_, lec) in keys}
        user_ids: Set[int] = {u for (u, _) in keys}

        weighted_category: float = self.item_weights.get("category_match", 0.0)
        weighted_rating: float = self.item_weights.get("review_rating", 0.0)

        # 1. 사용자 선호 카테고리 일치 점수
        if weighted_category > 0:
            user_prefer_map: DefaultDict[int, Set[int]] = defaultdict(set)
            user_prefers: List[Tuple[int, int]] = list(
                UserPreferCategory.objects.filter(user_id__in=user_ids).values_list("user_id", "category_id")
            )
            for u, c in user_prefers:
                user_prefer_map[u].add(c)

            lecture_category_map: Dict[int, Set[int]] = self.get_lecture_category_map()

            for u, lec in keys:
                # 사용자 선호 카테고리 & 강의 카테고리 교집합
                matched: Set[int] = user_prefer_map[u].intersection(lecture_category_map.get(lec, set()))
                if matched:
                    # 일치하는 카테고리 수 * 가중치
                    scores[(u, lec)] += len(matched) * weighted_category

        # 2. 강의 평균 평점 점수
        if weighted_rating > 0:
            avg_ratings = CrawledLecture.objects.filter(id__in=lec_ids).values("id", "average_rating")
            # None이 아닌 유효 평점만 딕셔너리로 매핑
            avg_map: Dict[int, float] = {
                r["id"]: float(r["average_rating"]) for r in avg_ratings if r["average_rating"] is not None
            }

            for u, lec in keys:
                if lec in avg_map and avg_map[lec] > 0:
                    # 평균 평점 * 가중치
                    scores[(u, lec)] += avg_map[lec] * weighted_rating

        return dict(scores)

    def _load_search_interactions(
        self,
        users: List[int],
        last_trained_at: Optional[datetime],
    ) -> Dict[Tuple[int, int], float]:
        """
        사용자 검색 로그를 강의 제목과 매칭하여 상호작용 점수 계산.
        최근 검색 로그 기간 제한 (SEARCH_LOG_DAYS_LIMIT) 및 감쇠 함수 적용.

        :param users: 대상 사용자 ID 리스트
        :param last_trained_at: 이전 학습 시점 (점진 학습 필터)
        :return: {(user_id, lecture_id): search_score} 딕셔너리
        """
        scores: DefaultDict[Tuple[int, int], float] = defaultdict(float)
        weighted_search: float = self.user_weights.get("search", 0.0)
        if weighted_search == 0:
            return {}

        # 검색 로그 조회 시작 시점 (기간 제한 적용)
        cutoff: datetime = self._now - timedelta(days=SEARCH_LOG_DAYS_LIMIT)
        query_filter: Q = Q(user_id__in=users, created_at__gte=cutoff)
        if last_trained_at:
            query_filter &= Q(created_at__gt=last_trained_at)

        recent_logs: List[Tuple[int, str, datetime]] = list(
            LectureSearchLog.objects.filter(query_filter)
            .values_list("user_id", "keyword", "created_at")
            .order_by("-created_at")
        )

        user_keyword_map: DefaultDict[int, Dict[str, datetime]] = defaultdict(dict)
        all_keywords: Set[str] = set()

        # 최근 검색 로그에서 키워드 추출 (중복 제거, 최신 기준)
        for user_id, keyword, created_at in recent_logs:
            if keyword and keyword not in user_keyword_map[user_id]:
                user_keyword_map[user_id][keyword] = created_at
                all_keywords.add(keyword)

        if not all_keywords:
            return {}

        # 키워드와 강의 제목 매칭을 위한 ORM 쿼리 구성 (OR 조건)
        keyword_query: Q = Q()
        for keyword in all_keywords:
            # 대소문자 구분 없이 제목 포함 검색
            keyword_query |= Q(title__icontains=keyword)

        matched_lectures_data: DefaultDict[int, List[str]] = defaultdict(list)
        if keyword_query:
            matched_lectures: List[Tuple[int, str]] = list(
                CrawledLecture.objects.filter(keyword_query).values_list("id", "title")
            )
            # 실제 제목에 키워드가 포함되는지 확인
            for lec_id, title in matched_lectures:
                for keyword in all_keywords:
                    if keyword.lower() in title.lower():
                        matched_lectures_data[lec_id].append(keyword)

        # 검색 점수 부여 및 감쇠 적용
        for user_id, keyword_data in user_keyword_map.items():
            for keyword, created_at in keyword_data.items():
                decay_factor: float = self._get_decay_factor(created_at)
                decayed_score: float = weighted_search * decay_factor

                for lec_id, matching_keywords in matched_lectures_data.items():
                    if keyword in matching_keywords:
                        # 동일 키워드가 매칭된 강의에 점수 부여
                        scores[(user_id, lec_id)] += decayed_score

        return dict(scores)

    # -- 3. 행렬 구축 함수 (Matrix Building)

    def build_user_item_matrix(
        self,
        users: Optional[List[int]] = None,
        last_trained_at: Optional[datetime] = None,
    ) -> MatrixBundle:
        """
        모든 상호작용 피처를 병합하여 사용자-아이템 희소 행렬 (COO Matrix) 생성.

        :param users: 학습에 사용할 특정 사용자 ID 리스트 (None 시 전체 사용자)
        :param last_trained_at: 이전 학습 시점 (점진 학습 필터링 기준)
        :return: MatrixBundle 타입 튜플 또는 None
        """
        # 데이터 로드 기준 시각 재설정
        self._now = timezone.now()

        # 전체 사용자 ID 리스트 로드 (Full training 시)
        if users is None:
            # 북마크를 남긴 모든 사용자 ID를 대상으로 함
            users_list: List[int] = list(LectureBookmark.objects.values_list("user_id", flat=True).distinct())
        else:
            users_list = users

        # 각 상호작용 피처 로드
        initial_interactions: Dict[Tuple[int, int], float] = self._load_user_interactions(users_list, last_trained_at)
        # 아이템 피처 로드를 위해 초기 상호작용 키를 전달
        item_feature_scores: Dict[Tuple[int, int], float] = self._load_item_features(
            initial_interactions, last_trained_at
        )
        search_scores: Dict[Tuple[int, int], float] = self._load_search_interactions(users_list, last_trained_at)

        # 모든 상호작용 점수 병합 (누적 합산)
        combined: DefaultDict[Tuple[int, int], float] = defaultdict(float)
        for data_dict in [initial_interactions, item_feature_scores, search_scores]:
            for k, v in data_dict.items():
                combined[k] += v

        if not combined:
            # 상호작용 데이터가 없으면 None 반환
            logger.info("No combined interaction data found for matrix building.")
            return None

        # 사용자/강의 ID를 고유 인덱스로 매핑
        all_users: List[int] = sorted(list(set(u for u, _ in combined.keys())))
        all_lectures: List[int] = sorted(list(set(l for _, l in combined.keys())))

        u_to_idx: Dict[int, int] = {u: i for i, u in enumerate(all_users)}
        l_to_idx: Dict[int, int] = {l: i for i, l in enumerate(all_lectures)}

        # 희소 행렬 데이터 구조
        rows: List[int] = []  # 사용자 인덱스
        cols: List[int] = []  # 강의 인덱스
        data: List[float] = []  # 상호작용 점수

        # 희소 행렬 데이터 구성
        for (u, l), score in combined.items():
            rows.append(u_to_idx[u])
            cols.append(l_to_idx[l])
            data.append(score)

        # COO Matrix (Coordinate Format) 생성
        matrix: coo_matrix = coo_matrix(
            (np.array(data, dtype=np.float32), (np.array(rows), np.array(cols))),
            shape=(len(all_users), len(all_lectures)),
            dtype=np.float32,  # 데이터 타입 명시
        )

        # 결과 튜플 반환
        return matrix, u_to_idx, l_to_idx, all_users, all_lectures
