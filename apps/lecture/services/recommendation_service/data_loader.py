import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import (
    DefaultDict,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Union,
)

import numpy as np
from django.core.cache import cache
from django.db import IntegrityError, OperationalError, ProgrammingError
from django.db.models import Q
from django.utils import timezone
from scipy.sparse import coo_matrix, csr_matrix

from apps.lecture.models import (
    CrawledLecture,
    LectureBookmark,
    LectureCategory,
    LectureSearchLog,
    UserPreferCategory,
)
from apps.lecture.services.recommendation_service.constants import (
    HALF_LIFE_DAYS,
    ITEM_FEATURE_WEIGHTS,
    LECTURE_CATEGORY_MAP_CACHE_KEY,
    LECTURE_CATEGORY_MAP_TIMEOUT,
    SEARCH_LOG_DAYS_LIMIT,
    USER_INTERACTION_WEIGHTS,
)
from apps.studies.models.groups import (
    GroupMember,
    StudyLecture,
)

logger: logging.Logger = logging.getLogger(__name__)

MatrixLike = Union[coo_matrix, csr_matrix]  # 희소 행렬 타입 유니온
# 행렬 구축 결과 반환 튜플 타입
MatrixBundleExtended = Optional[
    Tuple[
        MatrixLike,  # 결과 희소 행렬 (coo_matrix | csr_matrix)
        Dict[int, int],  # 사용자 ID -> 행렬 인덱스 맵
        Dict[int, int],  # 강의 ID -> 행렬 인덱스 맵
        List[int],  # 행렬에 포함된 사용자 ID 리스트 (정렬됨)
        List[int],  # 행렬에 포함된 강의 ID 리스트 (정렬됨)
        bool,  # 신규 사용자 포함 여부 (Partial Fit 시 사용)
    ]
]


def _normalize_sparse_rows_l1(matrix: MatrixLike, return_format: str = "coo") -> MatrixLike:
    """
    Scipy 희소 행렬의 각 행(사용자)을 L1 norm (합계 1)으로 안전하게 정규화
    CSR 포맷과 NumPy 벡터화를 사용해 성능 최적화
    return_format: 'coo' (기본값) 또는 'csr'
    """

    if matrix.shape[0] == 0:
        # 빈 행렬 처리: 반환 포맷에 맞춰 빈 행렬 반환
        return matrix.tocsr() if return_format == "csr" else matrix.tocoo()

    csr = matrix.tocsr()  # CSR 포맷으로 변환 (행 기반 연산 최적화)

    # 1. 각 행의 합계(L1 norm)를 계산하며 np.float32 dtype으로 고정
    row_sums = np.array(csr.sum(axis=1), dtype=np.float32).flatten()

    # 2. 0이 아닌 행의 역수를 계산 (0으로 나누기 방지)
    nonzero_rows = row_sums != 0
    inv_row_sums = np.zeros_like(row_sums, dtype=np.float32)
    inv_row_sums[nonzero_rows] = 1.0 / row_sums[nonzero_rows]

    # 각 행의 길이 (데이터 포인트 수) 계산
    # np.diff(csr.indptr)는 각 행의 0이 아닌 요소 수를 제공
    row_lengths = np.diff(csr.indptr).astype(np.int32, copy=False)

    # 3. 벡터화된 정규화 계수(inv_row_sums)를 데이터에 곱함
    # np.repeat으로 각 행의 정규화 계수를 해당 행의 데이터 수만큼 반복하여 CSR data 배열과 일치시킴
    csr.data *= np.repeat(inv_row_sums, row_lengths)

    # 요청된 포맷으로 변환하여 반환
    return csr if return_format == "csr" else csr.tocoo()


class DataLoader:
    """
    ALS 학습용 데이터 전처리, 캐싱, 상호작용 피처 엔지니어링 및 행렬 구축 담당
    시간 감쇠와 Partial Fit을 지원하여 실시간 업데이트 최적화
    """

    def __init__(self) -> None:
        # 사용자 상호작용 가중치 (불변 객체)
        self.user_weights: Dict[str, float] = USER_INTERACTION_WEIGHTS
        # 아이템 피처 가중치 (불변 객체)
        self.item_weights: Dict[str, float] = ITEM_FEATURE_WEIGHTS

        # 강의-카테고리 맵 메모리 캐시, TTL (Time To Live)
        self._lecture_category_map: Optional[Dict[int, Set[int]]] = None
        self._lecture_category_map_ttl: Optional[datetime] = None

        # 데이터 로드 및 시간 감쇠 기준 시각 (인스턴스 생성 시점)
        self._now: datetime = timezone.now()

    def _get_decay_factor(self, created_at: datetime) -> float:
        """
        단일 시간 감쇠: 경과일수 기반 점수감쇠 공식 적용
        0.5 ** (경과일수 / 반감기)
        """
        days_since: float = (self._now - created_at).total_seconds() / 86400  # 경과일수 계산
        return float(0.5 ** (days_since / HALF_LIFE_DAYS))

    def _get_decay_factor_array(self, days_since: np.ndarray) -> np.ndarray:
        """벡터 감쇠: 대량 로그 batch 처리 최적화 (NumPy 배열 입력)"""
        return np.power(0.5, days_since / HALF_LIFE_DAYS)

    @staticmethod
    def _load_lecture_category_map() -> Dict[int, Set[int]]:
        """DB에서 모든 강의별 카테고리 ID 집합을 로드"""
        lecture_category_map: DefaultDict[int, Set[int]] = defaultdict(set)
        # (lecture_id, category_id) 쌍을 DB에서 조회
        values_list: List[Tuple[int, int]] = list(LectureCategory.objects.values_list("lecture_id", "category_id"))
        for lec_id, cat_id in values_list:
            lecture_category_map[lec_id].add(cat_id)  # 강의 ID별 카테고리 ID 집합 생성
        return dict(lecture_category_map)

    def get_lecture_category_map(self) -> Dict[int, Set[int]]:
        """강의-카테고리 맵 로드/캐싱: 메모리→캐시→DB 순서로 시도"""
        now: datetime = timezone.now()

        # 1. 메모리 캐시 TTL 만료 체크
        if (
            self._lecture_category_map is not None
            and self._lecture_category_map_ttl
            and self._lecture_category_map_ttl > now
        ):
            return self._lecture_category_map

        # 2. Redis/Django 캐시 로드
        cached_data: Optional[Dict[int, List[int]]] = cache.get(LECTURE_CATEGORY_MAP_CACHE_KEY)
        if cached_data is not None:
            try:
                # 캐시에서 List로 로드 후 Set으로 복원 (캐시 호환성 문제 처리)
                result: Dict[int, Set[int]] = {k: set(v) for k, v in cached_data.items()}
                self._lecture_category_map = result
                self._lecture_category_map_ttl = now + timedelta(seconds=LECTURE_CATEGORY_MAP_TIMEOUT)
                return result

            except Exception as e:
                logger.warning("[CACHE] 강의-카테고리 맵 캐시 오류. 재로드. Error: %s", e)
                cache.delete(LECTURE_CATEGORY_MAP_CACHE_KEY)  # 캐시 손상 시 삭제

        # 3. 캐시 미존재, DB 직접 로드
        lecture_category_map: Dict[int, Set[int]] = DataLoader._load_lecture_category_map()
        try:
            # DB에서 로드한 Set을 List로 변환하여 캐싱 (캐시 라이브러리 호환성 확보)
            cache_friendly_map = {k: list(v) for k, v in lecture_category_map.items()}
            cache.set(
                LECTURE_CATEGORY_MAP_CACHE_KEY,
                cache_friendly_map,
                LECTURE_CATEGORY_MAP_TIMEOUT,
            )
        except Exception as e:
            logger.error("[CACHE_FAIL] 강의-카테고리 캐싱 실패: %s", e)

        # 메모리 캐시 업데이트
        self._lecture_category_map = lecture_category_map
        self._lecture_category_map_ttl = now + timedelta(seconds=LECTURE_CATEGORY_MAP_TIMEOUT)
        return lecture_category_map

    def _load_user_interactions(
        self,
        last_trained_at: Optional[datetime],
    ) -> Dict[Tuple[int, int], float]:
        """유저별 강의 상호작용 점수 (북마크, 스터디 참여) 계산"""
        # last_trained_at 이후의 상호작용만 로드하여 Partial Fit 지원
        interactions: DefaultDict[Tuple[int, int], float] = defaultdict(float)
        weighted_bookmark: float = self.user_weights.get("bookmark", 0.0)
        weighted_study: float = self.user_weights.get("study_participation", 0.0)

        query_filter: Q = Q()
        if last_trained_at:
            # Partial Fit: 마지막 학습 시각 이후 생성된 상호작용만 조회
            query_filter &= Q(created_at__gt=last_trained_at)

        # 북마크 상호작용
        if weighted_bookmark > 0:
            bookmarks_qs = LectureBookmark.objects.filter(query_filter)
            bookmarks: List[Tuple[int, int]] = list(bookmarks_qs.values_list("user_id", "lecture_id"))
            for user_id, lec_id in bookmarks:
                interactions[(user_id, lec_id)] += weighted_bookmark  # 고정 가중치 누적

        # 스터디 참여 상호작용 (시간 감쇠 적용)
        if weighted_study > 0:
            try:
                # GroupMember에 대한 Partial Fit 필터
                member_filter: Q = Q()
                if last_trained_at:
                    member_filter &= Q(created_at__gt=last_trained_at)

                members_qs = GroupMember.objects.filter(member_filter)

                # 관련 스터디 그룹 ID 추출
                study_group_ids: List[int] = list(members_qs.values_list("study_group_id", flat=True).distinct())

                # 추출된 그룹의 모든 멤버 로드
                group_members_qs = GroupMember.objects.filter(study_group_id__in=study_group_ids)

                # 그룹 ID -> 사용자 ID 집합 맵 생성
                group_user_map: DefaultDict[int, Set[int]] = defaultdict(set)
                for gm in group_members_qs:
                    group_user_map[gm.study_group_id].add(gm.user_id)

                # 스터디에 할당된 강의 및 생성 시각 로드
                study_participations: List[Tuple[int, int, datetime]] = list(
                    StudyLecture.objects.filter(study_group_id__in=study_group_ids).values_list(
                        "study_group_id", "lecture_id", "created_at"
                    )
                )

                # 벡터화를 위한 데이터 준비
                created_times: np.ndarray = np.array([sp[2].timestamp() for sp in study_participations])
                days_since: np.ndarray = (self._now.timestamp() - created_times) / 86400  # 경과일수
                decay_factors: np.ndarray = self._get_decay_factor_array(days_since)  # 벡터 감쇠 계산

                # 스터디 참여 점수 부여 (그룹 멤버 모두에게 점수 부여)
                for i, (grp_id, lec_id, _) in enumerate(study_participations):
                    decayed_score: float = weighted_study * decay_factors[i]
                    for user_id in group_user_map.get(grp_id, set()):
                        interactions[(user_id, lec_id)] += decayed_score

            except (ProgrammingError, OperationalError, IntegrityError) as e:
                logger.error("[DB] 스터디 참여 로드 오류: %s", e, exc_info=True)

        return dict(interactions)

    def _load_item_features(
        self,
        all_interactions: Dict[Tuple[int, int], float],
        last_trained_at: Optional[datetime],
    ) -> Dict[Tuple[int, int], float]:
        """강의 피처 점수(선호 카테고리 일치, 리뷰 평점)를 상호작용에 추가"""
        scores: DefaultDict[Tuple[int, int], float] = defaultdict(float)
        keys: Set[Tuple[int, int]] = set(all_interactions.keys())  # 상호작용 발생한 (유저, 강의) 쌍
        lec_ids: Set[int] = {lec for (_, lec) in keys}  # 관련 강의 ID 집합
        user_ids: Set[int] = {u for (u, _) in keys}  # 관련 사용자 ID 집합
        weighted_category: float = self.item_weights.get("category_match", 0.0)
        weighted_rating: float = self.item_weights.get("review_rating", 0.0)

        try:
            # 1. 사용자-선호 카테고리 일치 피처
            if weighted_category > 0:
                user_prefer_map: DefaultDict[int, Set[int]] = defaultdict(set)
                user_prefers: List[Tuple[int, int]] = list(
                    UserPreferCategory.objects.filter(user_id__in=user_ids).values_list("user_id", "category_id")
                )
                for u, c in user_prefers:
                    user_prefer_map[u].add(c)

                lecture_category_map: Dict[int, Set[int]] = (
                    self.get_lecture_category_map()
                )  # 캐시/DB에서 강의-카테고리 맵 로드

                # 상호작용이 있는 (유저, 강의) 쌍에 대해 피처 점수 부여
                for u, lec in keys:
                    # 유저의 선호 카테고리와 강의 카테고리의 교집합
                    matched: Set[int] = user_prefer_map[u].intersection(lecture_category_map.get(lec, set()))
                    if matched:
                        # 일치하는 카테고리 수 * 가중치
                        scores[(u, lec)] += len(matched) * weighted_category

            # 2. 강의별 리뷰 평점 피처
            if weighted_rating > 0:
                # 관련 강의의 평균 평점 조회
                avg_ratings = CrawledLecture.objects.filter(id__in=lec_ids).values("id", "average_rating")
                avg_map: Dict[int, float] = {
                    r["id"]: float(r["average_rating"]) for r in avg_ratings if r["average_rating"] is not None
                }

                # 상호작용이 있는 (유저, 강의) 쌍에 대해 피처 점수 부여
                for u, lec in keys:
                    if lec in avg_map and avg_map[lec] > 0:
                        # 평균 평점 * 가중치
                        scores[(u, lec)] += avg_map[lec] * weighted_rating

        except (ProgrammingError, OperationalError, IntegrityError) as e:
            logger.error("[DB] 아이템 피처 로드 오류: %s", e, exc_info=True)
            return {}

        return dict(scores)

    def _load_search_interactions(
        self,
        last_trained_at: Optional[datetime],
    ) -> Dict[Tuple[int, int], float]:
        """검색 기반 상호작용 점수 산출 (키워드-강의 매칭 및 시간 감쇠 적용)"""
        scores: DefaultDict[Tuple[int, int], float] = defaultdict(float)
        weighted_search: float = self.user_weights.get("search", 0.0)
        if weighted_search == 0:
            return {}

        try:
            # 검색 로그 조회 시작 시점 (기간 제한 적용)
            cutoff: datetime = self._now - timedelta(days=SEARCH_LOG_DAYS_LIMIT)
            query_filter: Q = Q(created_at__gte=cutoff)  # 기간 제한
            if last_trained_at:
                query_filter &= Q(created_at__gt=last_trained_at)  # Partial Fit 제한

            recent_logs_qs = LectureSearchLog.objects.filter(query_filter)

            # 검색 로그 (user_id, keyword, created_at) 조회
            recent_logs: List[Tuple[int, str, datetime]] = list(
                recent_logs_qs.values_list("user_id", "keyword", "created_at").order_by("-created_at")  # 최신순
            )

            user_keyword_map: DefaultDict[int, Dict[str, datetime]] = defaultdict(dict)
            all_keywords: Set[str] = set()

            # 사용자별 최근 검색 키워드 추출 (중복 제거, 최신 기준)
            for user_id, keyword, created_at in recent_logs:
                if keyword and keyword not in user_keyword_map[user_id]:
                    user_keyword_map[user_id][keyword] = created_at
                    all_keywords.add(keyword)
            if not all_keywords:
                return {}

            # 키워드와 강의 제목 매칭을 위한 ORM 쿼리 구성
            keyword_query: Q = Q()
            for keyword in all_keywords:
                # 대소문자 구분 없이 제목 포함 검색 (title__icontains)
                keyword_query |= Q(title__icontains=keyword)

            # 키워드와 매칭되는 강의 로드
            matched_lectures_data: DefaultDict[int, List[str]] = defaultdict(list)
            if keyword_query:
                matched_lectures: List[Tuple[int, str]] = list(
                    CrawledLecture.objects.filter(keyword_query).values_list("id", "title")
                )
                # 실제 제목에 키워드가 포함되는지 최종 확인
                for lec_id, title in matched_lectures:
                    for keyword in all_keywords:
                        if keyword.lower() in title.lower():
                            matched_lectures_data[lec_id].append(keyword)

            # 검색 점수 부여 및 감쇠 적용
            for user_id, keyword_data in user_keyword_map.items():
                for keyword, created_at in keyword_data.items():
                    decay_factor: float = self._get_decay_factor(created_at)  # 시간 감쇠
                    decayed_score: float = weighted_search * decay_factor

                    # 매칭되는 강의에 점수 누적
                    for lec_id, matching_keywords in matched_lectures_data.items():
                        if keyword in matching_keywords:
                            # 동일 키워드가 매칭된 강의에 점수 부여
                            scores[(user_id, lec_id)] += decayed_score

        except (ProgrammingError, OperationalError, IntegrityError) as e:
            logger.error("[DB] 검색 상호작용 로드 오류: %s", e, exc_info=True)
            return {}

        return dict(scores)

    def build_user_item_matrix(
        self,
        existing_users: Optional[List[int]] = None,
        last_trained_at: Optional[datetime] = None,
        normalize_rows: bool = True,
        return_format: str = "coo",
    ) -> MatrixBundleExtended:
        """모든 상호작용 피처를 병합하고 희소 행렬 구축"""
        # Partial Fit 시 신규 사용자를 식별하고 포함
        self._now = timezone.now()  # 현재 시각 업데이트

        is_partial_fit: bool = existing_users is not None  # Partial Fit 여부

        # 1. 대상 사용자 ID 리스트 로드 및 신규 사용자 확인
        if is_partial_fit:
            # Partial Fit: 마지막 학습 시점 이후 상호작용이 있는 사용자 ID 수집
            cutoff: datetime = self._now - timedelta(days=SEARCH_LOG_DAYS_LIMIT)  # 검색 로그 기간 제한

            # 북마크, 검색 로그, 스터디 멤버에서 신규/갱신 사용자 ID 수집
            user_ids_from_bookmarks: Set[int] = set(
                LectureBookmark.objects.filter(created_at__gt=last_trained_at).values_list("user_id", flat=True)
            )
            user_ids_from_searches: Set[int] = set(
                LectureSearchLog.objects.filter(created_at__gt=last_trained_at, created_at__gte=cutoff).values_list(
                    "user_id", flat=True
                )
            )
            user_ids_from_studies: Set[int] = set(
                GroupMember.objects.filter(created_at__gt=last_trained_at).values_list("user_id", flat=True)
            )

            all_interacting_users: Set[int] = user_ids_from_bookmarks | user_ids_from_searches | user_ids_from_studies

            existing_users_set: Set[int] = set(existing_users or [])

            new_users_in_interactions: Set[int] = (
                all_interacting_users - existing_users_set
            )  # 기존 사용자 목록에 없는 사용자
            users_list = sorted(list(existing_users_set | new_users_in_interactions))  # 기존 + 신규 사용자
            is_new_user_added = bool(new_users_in_interactions)  # 신규 사용자 추가 여부

        else:
            # Full Training: 모든 북마크 사용자 로드
            users_list = list(LectureBookmark.objects.values_list("user_id", flat=True).distinct())
            is_new_user_added = False

        # 2. 상호작용 피처 로드 (last_trained_at을 사용하여 Partial Fit 데이터만 로드)
        initial_interactions: Dict[Tuple[int, int], float] = self._load_user_interactions(last_trained_at)
        item_feature_scores: Dict[Tuple[int, int], float] = self._load_item_features(
            initial_interactions, last_trained_at
        )
        search_scores: Dict[Tuple[int, int], float] = self._load_search_interactions(last_trained_at)

        # 3. 모든 상호작용 점수 병합 (Counter를 사용하여 딕셔너리 값 합산)
        combined: Counter[Tuple[int, int]] = sum(
            map(Counter, [initial_interactions, item_feature_scores, search_scores]), Counter()
        )

        if not combined:
            logger.info("No combined interaction data found for matrix building.")
            return None  # 데이터 없을 시 None 반환

        # 4. 행렬 매핑 및 데이터 구성
        all_users: List[int] = users_list
        all_lectures: List[int] = sorted({l for _, l in combined.keys()})  # 상호작용 발생한 모든 강의 ID

        # ID -> 행렬 인덱스 맵 생성
        u_to_idx: Dict[int, int] = {u: i for i, u in enumerate(all_users)}
        l_to_idx: Dict[int, int] = {l: i for i, l in enumerate(all_lectures)}

        rows: List[int] = []  # 행 인덱스 (사용자)
        cols: List[int] = []  # 열 인덱스 (강의)
        data: List[float] = []  # 값 (상호작용 점수)

        for (u, l), score in combined.items():
            if u in u_to_idx and l in l_to_idx:  # 행렬에 포함되는 유저/강의만 사용
                rows.append(u_to_idx[u])
                cols.append(l_to_idx[l])
                data.append(score)

        # COO Matrix (Coordinate Format) 생성
        matrix: coo_matrix = coo_matrix(
            (np.array(data, dtype=np.float32), (np.array(rows), np.array(cols))),
            shape=(len(all_users), len(all_lectures)),
            dtype=np.float32,
        )

        # 행렬 행별 합 1로 정규화
        if normalize_rows and matrix.shape[0] > 0:
            # L1 정규화 함수 사용, 요청된 포맷으로 변환
            final_matrix = _normalize_sparse_rows_l1(matrix, return_format=return_format)
        else:
            # 정규화하지 않거나 빈 행렬인 경우, 요청된 포맷으로 변환
            final_matrix = matrix.tocsr() if return_format == "csr" else matrix.tocoo()

        # 결과 튜플 반환
        return final_matrix, u_to_idx, l_to_idx, all_users, all_lectures, is_new_user_added
