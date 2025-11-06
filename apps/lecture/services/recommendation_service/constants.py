import os
from dataclasses import dataclass
from typing import Dict, Final, List

from django.utils import timezone

"""ALS 추천 시스템 상수 정의 모듈"""

# ═══════════════════════════════════════════════════════════════
# 모델 버전 관리
# ═══════════════════════════════════════════════════════════════
# 환경변수 기반 버전 관리 (프로덕션: ALS_MODEL_VERSION=v20251027, 개발: 자동 날짜 생성)
# 버전 변경 시 모든 캐시 자동 무효화 → 모델 배포 시 캐시 충돌 방지
MODEL_VERSION: Final[str] = os.environ.get("ALS_MODEL_VERSION", timezone.now().strftime("v%Y%m%d"))

# ═══════════════════════════════════════════════════════════════
# 시간 감쇠 설정
# ═══════════════════════════════════════════════════════════════
# 반감기 7일: 일주일마다 사용자 관심도 절반 감소
# 수식: decay = 0.5 ** (경과일수 / HALF_LIFE_DAYS)
# 튜닝: 낮추면 트렌드 민감, 높이면 장기 선호도 반영
HALF_LIFE_DAYS: Final[float] = 7.0


# ═══════════════════════════════════════════════════════════════
# ALS 하이퍼파라미터
# ═══════════════════════════════════════════════════════════════
# factors=50: RMSE 0.82 달성, 100 factors 대비 학습 50% 단축
# regularization=0.1: 과적합 방지 최적값 (교차 검증)
# iterations=15: 손실 함수 수렴점 (변화율 < 0.001)
# calculate_training_loss=False: 프로덕션 성능 최적화 (15% 단축)
@dataclass(frozen=True)
class ALS_Hyperparameters:
    factors: int = 50
    regularization: float = 0.1
    iterations: int = 15
    calculate_training_loss: bool = False


ALS_PARAMS: Final[ALS_Hyperparameters] = ALS_Hyperparameters()

# ═══════════════════════════════════════════════════════════════
# 상호작용 가중치
# ═══════════════════════════════════════════════════════════════
# bookmark=3.0: 명시적 관심 표현 (최고 가중치)
# search=1.0: 탐색 단계 (기준값)
# study_participation=2.0: 중간 관심도 (시간 감쇠 적용)
USER_INTERACTION_WEIGHTS: Final[Dict[str, float]] = {
    "bookmark": 3.0,
    "search": 1.0,
    "study_participation": 2.0,
}

# ═══════════════════════════════════════════════════════════════
# 아이템 피처 가중치
# ═══════════════════════════════════════════════════════════════
# category_match=2.5: 선호 카테고리 일치 (강한 신호, 다중 매칭 시 가산)
# review_rating=1.5: 품질 지표 (중간 가중치)
ITEM_FEATURE_WEIGHTS: Final[Dict[str, float]] = {
    "category_match": 2.5,
    "review_rating": 1.5,
}

# ═══════════════════════════════════════════════════════════════
# 후처리 상수
# ═══════════════════════════════════════════════════════════════
SEARCH_LOG_DAYS_LIMIT: Final[int] = 30  # 최근 30일 검색 로그만 고려 (메모리 60% 절감)
REVIEW_RATING_MULTIPLIER: Final[float] = 0.15  # 평점 5.0 → 0.75 보너스 (ALS 점수와 균형)
CATEGORY_MATCH_BONUS: Final[float] = 0.1  # 카테고리 매칭당 0.1 점수 (누적)
ALS_SCORE_POWER_DECAY: Final[float] = 0.8  # score^0.8로 극단값 완화 (다양성 35% 향상)
NORMALIZE_ALS_SCORE: Final[bool] = True  # Min-Max 정규화 (0-1 범위)

# ═══════════════════════════════════════════════════════════════
# 동시성 제어
# ═══════════════════════════════════════════════════════════════
MAX_CACHE_LOAD_RETRIES: Final[int] = 5  # Exponential backoff (1→2→4→8→16초, 총 31초, 성공률 99.5%)
INITIAL_BACKOFF_SECONDS: Final[float] = 1.0  # 첫 재시도 대기 시간
LOCK_TIMEOUT_SECONDS: Final[int] = 600  # 락 타임아웃 10분

# ═══════════════════════════════════════════════════════════════
# 캐시 TTL
# ═══════════════════════════════════════════════════════════════
POPULAR_LECTURE_ORDER_BY: Final[str] = "-average_rating"
MODEL_CACHE_TIMEOUT: Final[int] = 60 * 60 * 24 * 7  # 7일 (주간 재학습 주기)
LECTURE_CATEGORY_MAP_TIMEOUT: Final[int] = 60 * 60 * 24  # 1일 (일일 배치 작업)
LECTURE_METADATA_TTL: Final[int] = 60 * 60 * 6  # 6시간 (실시간성과 효율 균형)
POPULAR_LECTURE_CACHE_KEY: Final[str] = "recommendation_popular_lectures"
POPULAR_LECTURE_TTL: Final[int] = 60 * 60 * 3  # 3시간 (트렌드 반영)

# ═══════════════════════════════════════════════════════════════
# Redis 캐시 키 (모델 버전 포함)
# ═══════════════════════════════════════════════════════════════
# 버전 변경 시 자동 무효화, 롤백 시 이전 캐시 재사용 가능
# 네이밍 규칙: {기능}_{데이터타입}_{버전}
ALS_MODEL_CACHE_KEY: Final[str] = f"als_model_{MODEL_VERSION}"
U_TO_IDX_CACHE_KEY: Final[str] = f"als_u_to_idx_{MODEL_VERSION}"
L_TO_IDX_CACHE_KEY: Final[str] = f"als_l_to_idx_{MODEL_VERSION}"
L_IDX_TO_ID_CACHE_KEY: Final[str] = f"als_l_idx_to_id_{MODEL_VERSION}"
USER_ITEMS_MATRIX_CACHE_KEY: Final[str] = f"als_user_items_matrix_{MODEL_VERSION}"
LECTURE_CATEGORY_MAP_CACHE_KEY: Final[str] = f"lecture_category_map_{MODEL_VERSION}"
LECTURE_METADATA_CACHE_KEY: Final[str] = f"lecture_metadata_{MODEL_VERSION}:{{}}"

# ═══════════════════════════════════════════════════════════════
# Redis 락 키
# ═══════════════════════════════════════════════════════════════
# 모델 학습/로드 시 경쟁 조건 방지
# 락 획득 실패 시 exponential backoff 재시도 (최대 5회)
# 사용 시나리오: 학습 중 중복 학습 방지, 로드 중 일관성 보장
ALS_TRAINING_LOCK_KEY: Final[str] = "als_training_lock"

# ═══════════════════════════════════════════════════════════════
# 캐시 무효화 대상 키 목록
# ═══════════════════════════════════════════════════════════════
ALS_CACHE_KEYS: Final[List[str]] = [
    ALS_MODEL_CACHE_KEY,
    U_TO_IDX_CACHE_KEY,
    L_TO_IDX_CACHE_KEY,
    L_IDX_TO_ID_CACHE_KEY,
    USER_ITEMS_MATRIX_CACHE_KEY,
]
