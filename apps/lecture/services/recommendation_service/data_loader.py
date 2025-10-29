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
    cast,
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

MatrixLike = Union[coo_matrix, csr_matrix]
MatrixBundleExtended = Optional[
    Tuple[
        MatrixLike,
        Dict[int, int],
        Dict[int, int],
        List[int],
        List[int],
        bool,
    ]
]


def _normalize_sparse_rows_l1(matrix: MatrixLike, return_format: str = "coo") -> MatrixLike:
    """
    Scipy 희소 행렬의 각 행(사용자)을 L1 norm (합계 1)으로 안전하게 정규화
    CSR 포맷과 NumPy 벡터화를 사용해 성능 최적화
    return_format: 'coo' (기본값) 또는 'csr'
    """
    if matrix.shape[0] == 0:
        return matrix.tocsr() if return_format == "csr" else matrix.tocoo()

    csr = matrix.tocsr()
    row_sums = np.array(csr.sum(axis=1), dtype=np.float32).flatten()

    nonzero_rows = row_sums != 0
    inv_row_sums = np.zeros_like(row_sums, dtype=np.float32)
    inv_row_sums[nonzero_rows] = 1.0 / row_sums[nonzero_rows]

    row_lengths = np.diff(csr.indptr).astype(np.int32, copy=False)
    csr.data *= np.repeat(inv_row_sums, row_lengths)

    return csr if return_format == "csr" else csr.tocoo()


class DataLoader:
    """
    ALS 학습용 데이터 전처리, 캐싱, 상호작용 피처 엔지니어링 및 행렬 구축 담당
    시간 감쇠와 Partial Fit을 지원하여 실시간 업데이트 최적화
    """

    def __init__(self) -> None:
        self.user_weights: Dict[str, float] = USER_INTERACTION_WEIGHTS
        self.item_weights: Dict[str, float] = ITEM_FEATURE_WEIGHTS

        # 강의-카테고리 맵 메모리 캐시
        self._lecture_category_map: Optional[Dict[int, Set[int]]] = None
        self._lecture_category_map_ttl: Optional[datetime] = None

    def _get_current_time(self) -> datetime:
        """현재 시각을 반환 (일관성 있는 시간 기준 제공)"""
        return timezone.now()

    def _get_decay_factor(self, created_at: datetime, reference_time: datetime) -> float:
        """
        단일 시간 감쇠: 경과일수 기반 점수감쇠 공식 적용
        0.5 ** (경과일수 / 반감기)

        Args:
            created_at: 상호작용 발생 시각
            reference_time: 기준 시각 (감쇠 계산의 현재 시점)
        """
        days_since: float = (reference_time - created_at).total_seconds() / 86400
        return float(0.5 ** (days_since / HALF_LIFE_DAYS))

    def _get_decay_factor_array(self, days_since: np.ndarray) -> np.ndarray:
        """벡터 감쇠: 대량 로그 batch 처리 최적화 (NumPy 배열 입력)"""
        return np.power(0.5, days_since / HALF_LIFE_DAYS)

    @staticmethod
    def _load_lecture_category_map() -> Dict[int, Set[int]]:
        """DB에서 모든 강의별 카테고리 ID 집합을 로드"""
        lecture_category_map: DefaultDict[int, Set[int]] = defaultdict(set)
        values_list: List[Tuple[int, int]] = list(LectureCategory.objects.values_list("lecture_id", "category_id"))
        for lec_id, cat_id in values_list:
            lecture_category_map[lec_id].add(cat_id)
        return dict(lecture_category_map)

    def get_lecture_category_map(self) -> Dict[int, Set[int]]:
        """강의-카테고리 맵 로드/캐싱: 메모리→캐시→DB 순서로 시도"""
        now: datetime = self._get_current_time()

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
                # 캐시 키 타입 안전성 확보: bytes, 문자열, 정수 모두 처리
                result: Dict[int, Set[int]] = {}
                for k, v in cached_data.items():
                    # bytes 타입 처리 추가
                    if isinstance(k, bytes):
                        lecture_id = int(k.decode("utf-8"))
                    elif isinstance(k, str):
                        lecture_id = int(k)
                    else:
                        lecture_id = k
                    result[lecture_id] = set(v)

                self._lecture_category_map = result
                self._lecture_category_map_ttl = now + timedelta(seconds=LECTURE_CATEGORY_MAP_TIMEOUT)
                return result
            except (ValueError, TypeError, AttributeError) as e:
                logger.warning(f"[CACHE] Failed to parse cached lecture category map: {e}")

        # 3. DB에서 로드
        try:
            lecture_category_map: Dict[int, Set[int]] = self._load_lecture_category_map()

            # 캐시에 저장 (Set을 List로 변환)
            cache_data: Dict[int, List[int]] = {
                lec_id: list(cat_ids) for lec_id, cat_ids in lecture_category_map.items()
            }
            cache.set(LECTURE_CATEGORY_MAP_CACHE_KEY, cache_data, LECTURE_CATEGORY_MAP_TIMEOUT)

            self._lecture_category_map = lecture_category_map
            self._lecture_category_map_ttl = now + timedelta(seconds=LECTURE_CATEGORY_MAP_TIMEOUT)
            return lecture_category_map
        except (ProgrammingError, OperationalError, IntegrityError) as e:
            logger.error(f"[DB] Failed to load lecture category map: {e}", exc_info=True)
            return {}

    def _load_user_interactions(
        self,
        last_trained_at: Optional[datetime],
        reference_time: datetime,
    ) -> Dict[Tuple[int, int], float]:
        """유저별 강의 상호작용 점수 (북마크, 스터디 참여) 계산"""
        interactions: DefaultDict[Tuple[int, int], float] = defaultdict(float)
        weighted_bookmark: float = self.user_weights.get("bookmark", 0.0)
        weighted_study: float = self.user_weights.get("study_participation", 0.0)

        query_filter: Q = Q()
        if last_trained_at:
            query_filter &= Q(created_at__gt=last_trained_at)

        # 북마크 상호작용
        if weighted_bookmark > 0:
            bookmarks_qs = LectureBookmark.objects.filter(query_filter)
            bookmarks: List[Tuple[int, int]] = list(bookmarks_qs.values_list("user_id", "lecture_id"))
            for user_id, lec_id in bookmarks:
                interactions[(user_id, lec_id)] += weighted_bookmark

        # 스터디 참여 상호작용 (시간 감쇠 적용)
        if weighted_study > 0:
            try:
                study_lecture_filter: Q = Q()
                if last_trained_at:
                    study_lecture_filter &= Q(created_at__gt=last_trained_at)

                study_participations: List[Tuple[int, int, datetime]] = list(
                    StudyLecture.objects.filter(study_lecture_filter).values_list(
                        "study_group_id", "lecture_id", "created_at"
                    )
                )

                if study_participations:
                    study_group_ids: List[int] = list({sp[0] for sp in study_participations})

                    # 그룹 멤버 로드 시 가입 시점 필터링 추가
                    group_members_qs = GroupMember.objects.filter(study_group_id__in=study_group_ids)

                    # 그룹별 멤버와 가입 시점 매핑
                    group_user_map: DefaultDict[int, Dict[int, datetime]] = defaultdict(dict)
                    for gm in group_members_qs:
                        group_user_map[gm.study_group_id][gm.user_id] = gm.created_at

                    created_times: np.ndarray = np.array([sp[2].timestamp() for sp in study_participations])
                    days_since: np.ndarray = (reference_time.timestamp() - created_times) / 86400
                    decay_factors: np.ndarray = self._get_decay_factor_array(days_since)

                    # 스터디 참여 점수 부여 (가입 시점 검증)
                    for i, (grp_id, lec_id, lecture_created_at) in enumerate(study_participations):
                        decayed_score: float = weighted_study * decay_factors[i]
                        for user_id, member_joined_at in group_user_map.get(grp_id, {}).items():
                            # 사용자가 그룹 가입 후 생성된 강의에만 점수 부여
                            if member_joined_at <= lecture_created_at:
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
        keys: Set[Tuple[int, int]] = set(all_interactions.keys())

        if not keys:
            return {}

        lec_ids: Set[int] = {lec for (_, lec) in keys}
        user_ids: Set[int] = {u for (u, _) in keys}
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

                lecture_category_map: Dict[int, Set[int]] = self.get_lecture_category_map()

                for u, lec in keys:
                    matched: Set[int] = user_prefer_map[u].intersection(lecture_category_map.get(lec, set()))
                    if matched:
                        scores[(u, lec)] += len(matched) * weighted_category

                        # 2. 강의별 리뷰 평점 피처
            if weighted_rating > 0:
                avg_ratings = CrawledLecture.objects.filter(id__in=lec_ids).values("id", "average_rating")
                avg_map: Dict[int, float] = {
                    r["id"]: float(r["average_rating"]) for r in avg_ratings if r["average_rating"] is not None
                }

                for u, lec in keys:
                    if lec in avg_map and avg_map[lec] > 0:
                        scores[(u, lec)] += avg_map[lec] * weighted_rating

        except (ProgrammingError, OperationalError, IntegrityError) as e:
            logger.error("[DB] 아이템 피처 로드 오류: %s", e, exc_info=True)
            return {}

        return dict(scores)

    def _load_search_interactions(
        self,
        last_trained_at: Optional[datetime],
        reference_time: datetime,
    ) -> Dict[Tuple[int, int], float]:
        """검색 기반 상호작용 점수 산출 (키워드-강의 매칭 및 시간 감쇠 적용)"""
        scores: DefaultDict[Tuple[int, int], float] = defaultdict(float)
        weighted_search: float = self.user_weights.get("search", 0.0)
        if weighted_search == 0:
            return {}

        try:
            # 검색 로그 조회 시작 시점 (기간 제한 적용)
            cutoff: datetime = reference_time - timedelta(days=SEARCH_LOG_DAYS_LIMIT)

            # Partial Fit 시 last_trained_at과 cutoff 중 더 최근 시점 사용
            if last_trained_at:
                effective_start = max(last_trained_at, cutoff)
                search_filter: Q = Q(created_at__gt=effective_start)
            else:
                search_filter = Q(created_at__gte=cutoff)

            recent_logs_qs = LectureSearchLog.objects.filter(search_filter)

            # 검색 로그 (user_id, keyword, created_at) 조회
            recent_logs: List[Tuple[int, str, datetime]] = list(
                recent_logs_qs.values_list("user_id", "keyword", "created_at").order_by("-created_at")
            )

            # 사용자별 키워드와 검색 빈도 추적
            user_keyword_map: DefaultDict[int, DefaultDict[str, List[datetime]]] = defaultdict(
                lambda: defaultdict(list)
            )
            all_keywords: Set[str] = set()

            # 사용자별 키워드 검색 이력 수집 (빈도 고려)
            for user_id, keyword, created_at in recent_logs:
                if keyword:
                    user_keyword_map[user_id][keyword].append(created_at)
                    all_keywords.add(keyword)

            if not all_keywords:
                return {}

                # 키워드와 강의 제목 매칭을 위한 ORM 쿼리 구성
            keyword_query: Q = Q()
            for keyword in all_keywords:
                keyword_query |= Q(title__icontains=keyword)

                # 키워드와 매칭되는 강의 로드
            matched_lectures_data: DefaultDict[int, Set[str]] = defaultdict(set)
            if keyword_query:
                matched_lectures: List[Tuple[int, str]] = list(
                    CrawledLecture.objects.filter(keyword_query).values_list("id", "title")
                )
                # 실제 제목에 키워드가 포함되는지 최종 확인
                for lec_id, title in matched_lectures:
                    title_lower = title.lower()
                    for keyword in all_keywords:
                        if keyword.lower() in title_lower:
                            matched_lectures_data[lec_id].add(keyword)

                            # 검색 점수 부여 및 감쇠 적용 (검색 빈도 반영)
            for user_id, keyword_data in user_keyword_map.items():
                for keyword, search_times in keyword_data.items():
                    # 각 검색 시점에 대해 감쇠 적용
                    for search_time in search_times:
                        decay_factor: float = self._get_decay_factor(search_time, reference_time)
                        decayed_score: float = weighted_search * decay_factor

                        # 매칭되는 강의에 점수 누적
                        for lec_id, matching_keywords in matched_lectures_data.items():
                            if keyword in matching_keywords:
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
        reference_time: datetime = self._get_current_time()

        is_partial_fit: bool = existing_users is not None
        is_new_user_added: bool = False

        # 1. 대상 사용자 ID 리스트 로드 및 신규 사용자 확인
        if is_partial_fit:
            # last_trained_at 유효성 확인
            if last_trained_at and last_trained_at.tzinfo is None:
                last_trained_at = timezone.make_aware(last_trained_at)

            if last_trained_at:
                existing_users_list = cast(List[int], existing_users)
                cutoff: datetime = reference_time - timedelta(days=SEARCH_LOG_DAYS_LIMIT)

                # Partial Fit 시 last_trained_at과 cutoff 중 더 최근 시점 사용
                effective_start = max(last_trained_at, cutoff)

                # 북마크, 검색 로그, 스터디 멤버에서 신규/갱신 사용자 ID 수집
                user_ids_from_bookmarks: Set[int] = set(
                    LectureBookmark.objects.filter(created_at__gt=last_trained_at).values_list("user_id", flat=True)
                )
                user_ids_from_searches: Set[int] = set(
                    LectureSearchLog.objects.filter(created_at__gt=effective_start).values_list("user_id", flat=True)
                )
                user_ids_from_studies: Set[int] = set(
                    GroupMember.objects.filter(created_at__gt=last_trained_at).values_list("user_id", flat=True)
                )

                all_interacting_users: Set[int] = (
                    user_ids_from_bookmarks | user_ids_from_searches | user_ids_from_studies
                )

                existing_users_set: Set[int] = set(existing_users_list)
                new_users_in_interactions: Set[int] = all_interacting_users - existing_users_set

                users_list: List[int] = existing_users_list + sorted(list(new_users_in_interactions))
                is_new_user_added = bool(new_users_in_interactions)

            else:
                # existing_users가 주어졌지만 last_trained_at이 없는 경우
                # Full Training으로 간주
                users_list = sorted(list(LectureBookmark.objects.values_list("user_id", flat=True).distinct()))
                is_partial_fit = False
        else:
            # Full Training: 모든 북마크 사용자 로드
            users_list = sorted(list(LectureBookmark.objects.values_list("user_id", flat=True).distinct()))
            is_new_user_added = False

        # 2. 상호작용 피처 로드 (일관된 reference_time 사용)
        initial_interactions: Dict[Tuple[int, int], float] = self._load_user_interactions(
            last_trained_at, reference_time
        )
        item_feature_scores: Dict[Tuple[int, int], float] = self._load_item_features(
            initial_interactions, last_trained_at
        )
        search_scores: Dict[Tuple[int, int], float] = self._load_search_interactions(last_trained_at, reference_time)

        # 3. 모든 상호작용 점수 병합
        combined: Counter[Tuple[int, int]] = sum(
            map(Counter, [initial_interactions, item_feature_scores, search_scores]),
            Counter(),
        )

        # 4. 빈 데이터 처리 (명확한 로직)
        if not combined:
            if is_partial_fit:
                # Partial Fit에서 신규 데이터 없음
                if not is_new_user_added:
                    logger.info("No combined interaction data found for partial fit.")
                    return None
                # 신규 사용자는 있지만 상호작용 없음 - 빈 행렬 생성하지 않고 None 반환
                logger.warning("New users detected but no interactions found. Returning None.")
                return None
            else:
                # Full Fit에서 데이터 없음
                if not users_list:
                    logger.info("No users found for matrix building.")
                    return None
                # 사용자는 있지만 상호작용 없음 - Cold Start 대비 빈 행렬 생성
                logger.warning("Users exist but no interactions found. Creating empty matrix for cold start.")
        # 5. 행렬 매핑 및 데이터 구성
        all_users: List[int] = users_list

        # 5.1 강의 ID 리스트 (행렬의 Column) 결정
        if not is_partial_fit:
            # 전체 학습 시: 모든 강의 ID를 포함 (Cold Start 대비)
            all_lectures = list(CrawledLecture.objects.values_list("id", flat=True).order_by("id"))
        else:
            # Partial Training 시: 상호작용 발생한 강의 ID만 포함
            # 주의: ModelTrainer에서 기존 모델과 Shape 일치 여부 검증 필요
            all_lectures = sorted({l for _, l in combined.keys()})

        # ID -> 행렬 인덱스 맵 생성
        u_to_idx: Dict[int, int] = {u: i for i, u in enumerate(all_users)}
        l_to_idx: Dict[int, int] = {l: i for i, l in enumerate(all_lectures)}

        rows: List[int] = []
        cols: List[int] = []
        data: List[float] = []

        for (u, l), score in combined.items():
            if u in u_to_idx and l in l_to_idx:
                rows.append(u_to_idx[u])
                cols.append(l_to_idx[l])
                data.append(score)

        # COO Matrix 생성
        matrix: coo_matrix = coo_matrix(
            (np.array(data, dtype=np.float32), (np.array(rows), np.array(cols))),
            shape=(len(all_users), len(all_lectures)),
            dtype=np.float32,
        )

        # 행렬 행별 L1 정규화
        if normalize_rows and matrix.shape[0] > 0:
            final_matrix = _normalize_sparse_rows_l1(matrix, return_format=return_format)
        else:
            final_matrix = matrix.tocsr() if return_format == "csr" else matrix.tocoo()

        return final_matrix, u_to_idx, l_to_idx, all_users, all_lectures, is_new_user_added
