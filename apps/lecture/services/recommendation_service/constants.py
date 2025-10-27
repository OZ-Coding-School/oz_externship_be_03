from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Final

"""ALS 모델 학습/예측 및 서비스 운영에서 사용하는 주요 상수 정의 모듈."""

# ──────────────────
"""모델 버전 관리: 배포 날짜 기반 자동 버전명 생성.
예: v20251027 (YYYYMMDD 형식)
"""
MODEL_VERSION: Final[str] = datetime.now().strftime("v%Y%m%d")

# ──────────────────
"""상호작용 점수 감쇠 관련 상수.
반감기(일 단위) - 시간 기반 점수 감소에 사용.

수학적 적용 예시:
    감쇠 계수 = 0.5 ** (경과일수 / HALF_LIFE_DAYS)
    또는
    f(t) = exp(-ln(2) * t / HALF_LIFE_DAYS)
    (t: 상호작용 이후 경과 일수, HALF_LIFE_DAYS: 반감기)
"""
HALF_LIFE_DAYS: Final[float] = 7.0

# ──────────────────
"""ALS 모델 학습 하이퍼파라미터 모음.
잠재 요인 수, 정규화 강도, 반복 횟수 등 모델 품질·비용 관련 파라미터 정의.
"""


@dataclass(frozen=True)
class ALS_Hyperparameters:
    factors: int = 50  # 잠재 요인 수
    regularization: float = 0.1  # L2 정규화 강도
    iterations: int = 15  # 에폭(데이터 순회 횟수)
    calculate_training_loss: bool = False  # 학습 손실 계산 여부


ALS_PARAMS: Final[ALS_Hyperparameters] = ALS_Hyperparameters()

# ──────────────────
"""사용자 상호작용별 가중치 설정.
각 상호작용은 추천 행렬 점수에 더해짐.
"""
USER_INTERACTION_WEIGHTS: Final[Dict[str, float]] = {
    "bookmark": 3.0,  # 강의 북마크: 높은 의도성
    "search": 1.0,  # 강의 검색: 낮은 의도성/최근성
    "study_participation": 2.0,  # 스터디 참여: 중간 의도성
}

# ──────────────────
"""아이템 피처별 점수 가중치.
추천 점수 후처리 및 행렬 구축에 사용.
"""
ITEM_FEATURE_WEIGHTS: Final[Dict[str, float]] = {
    "category_match": 2.5,  # 사용자가 선호하는 카테고리와 강의 카테고리 일치 가중치
    "review_rating": 1.5,  # 리뷰 평점에 부여할 가중치
}

# ──────────────────
"""검색·평점·카테고리·ALS 관련 후처리 상수"""
SEARCH_LOG_DAYS_LIMIT: Final[int] = 30  # 최근 검색 로그 기간 제한 (일)
REVIEW_RATING_MULTIPLIER: Final[float] = 0.15  # 평점 보너스 스케일
CATEGORY_MATCH_BONUS: Final[float] = 0.1  # 카테고리 일치 추가 보너스
ALS_SCORE_POWER_DECAY: Final[float] = 0.8  # ALS 점수 감쇠 지수 (score^0.8)
NORMALIZE_ALS_SCORE: Final[bool] = True  # ALS 점수 min-max 정규화 여부

# ──────────────────
"""캐시 및 Redis 락, 동시성 제어 관련 상수"""
MAX_CACHE_LOAD_RETRIES: Final[int] = 5
INITIAL_BACKOFF_SECONDS: Final[float] = 1.0

# ──────────────────
"""강의, 모델 캐시 관련 상수 및 TTL"""
POPULAR_LECTURE_ORDER_BY: Final[str] = "-average_rating"
MODEL_CACHE_TIMEOUT: Final[int] = 60 * 60 * 24 * 7  # 7일
LECTURE_CATEGORY_MAP_TIMEOUT: Final[int] = 60 * 60 * 24  # 1일
LECTURE_METADATA_TTL: Final[int] = 60 * 60 * 6  # 6시간

# ──────────────────
"""추가: 인기 강의 리스트 캐싱용 Redis 키 및 TTL"""
POPULAR_LECTURE_CACHE_KEY: Final[str] = "recommendation_popular_lectures"
POPULAR_LECTURE_TTL: Final[int] = 60 * 60 * 3  # 3시간 TTL

# ──────────────────
"""Redis 캐시 키(모델 버전 포함). 캐시 무효화/재생성에 사용."""
ALS_MODEL_CACHE_KEY: Final[str] = f"als_model_{MODEL_VERSION}"
U_TO_IDX_CACHE_KEY: Final[str] = f"als_u_to_idx_{MODEL_VERSION}"
L_TO_IDX_CACHE_KEY: Final[str] = f"als_l_to_idx_{MODEL_VERSION}"
L_IDX_TO_ID_CACHE_KEY: Final[str] = f"als_l_idx_to_id_{MODEL_VERSION}"
USER_ITEMS_MATRIX_CACHE_KEY: Final[str] = f"als_user_items_matrix_{MODEL_VERSION}"
LECTURE_CATEGORY_MAP_CACHE_KEY: Final[str] = f"lecture_category_map_{MODEL_VERSION}"
LECTURE_METADATA_CACHE_KEY: Final[str] = f"lecture_metadata_{MODEL_VERSION}:{{}}"

# ──────────────────
"""ALS 모델 학습/로드/캐시 시 동시성 제어를 위한 Redis 락 키"""
ALS_TRAINING_LOCK_KEY: Final[str] = "als_training_lock"
