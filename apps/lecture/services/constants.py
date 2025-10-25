from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Final

# 모델 버전 관리: 수동 대신 현재 날짜 기반으로 자동 생성 (YYYYMMDD)
# 형식: 'vYYYYMMDD' (예: v20251026)
MODEL_VERSION: Final[str] = datetime.now().strftime("v%Y%m%d")

# 시간 기반 감쇠 함수 (Time-based Decay Function)의 반감기 (일 단위)
# 반감기: 7.0일 (스코어가 절반으로 줄어드는 데 걸리는 기간)
HALF_LIFE_DAYS: Final[float] = 7.0


# ALS 하이퍼파라미터 (ALS Hyperparameters)
@dataclass(frozen=True)
class ALS_Hyperparameters:
    """ALS 모델 학습에 사용되는 하이퍼파라미터 정의"""

    factors: int = 50  # 잠재 요인(Latent Factors) 수: 추천 품질과 학습 비용 사이의 균형점
    regularization: float = 0.1  # 정규화 계수(Lambda): 과적합 방지를 위한 L2 정규화 강도
    iterations: int = 15  # 학습 반복 횟수(Epochs): 학습 데이터 순회 횟수
    calculate_training_loss: bool = False  # 학습 손실 계산 여부: True 시 오버헤드 발생 가능


# 최종 ALS 파라미터 객체
ALS_PARAMS: Final[ALS_Hyperparameters] = ALS_Hyperparameters()


# 사용자 상호작용 피드백 점수화 가중치
# 상호작용 발생 시 최종 상호작용 행렬에 더해질 가중치
USER_INTERACTION_WEIGHTS: Final[Dict[str, float]] = {
    "bookmark": 3.0,  # 강의 북마크: 높은 의도성 반영
    "search": 1.0,  # 강의 검색: 낮은 의도성, 최근성 중요
    "study_participation": 2.0,  # 스터디 참여: 중간 수준 의도성 반영
}

# 아이템 피처 가중치 (추천 점수 후처리 및 상호작용 행렬 구축에 사용)
ITEM_FEATURE_WEIGHTS: Final[Dict[str, float]] = {
    "category_match": 2.5,  # 사용자 선호 카테고리와 강의 카테고리 일치 시 가중치
    "review_rating": 1.5,  # 강의의 리뷰 평점(Average Rating)에 부여할 가중치
}

# 로직 및 폴백 관련 상수 (Logic & Fallback Constants)
SEARCH_LOG_DAYS_LIMIT: Final[int] = 30  # 최근 검색 로그 조회 기간 (일 단위): 이 기간 내의 로그만 사용
REVIEW_RATING_MULTIPLIER: Final[float] = 0.15  # 평점 보너스 비율 안정화: 평점 점수의 최종 스케일링 계수
CATEGORY_MATCH_BONUS: Final[float] = 0.1  # 추천 점수 후처리 시 카테고리 일치에 부여하는 보너스 값
ALS_SCORE_POWER_DECAY: Final[float] = 0.8  # ALS 점수 비선형 감쇠 지수: ALS 예측 점수 ** 0.8 적용 (점수 평탄화 목적)
NORMALIZE_ALS_SCORE: Final[bool] = True  # ALS 점수를 0~1 사이로 정규화할지 여부: True 시 Min-Max 정규화 적용

# 캐시 및 동시성 제어 상수 (Cache & Concurrency Control)
MAX_CACHE_LOAD_RETRIES: Final[int] = 5  # Redis 락 획득 대기 최대 재시도 횟수
INITIAL_BACKOFF_SECONDS: Final[float] = 1.0  # 초기 백오프 시간 (초): 재시도 간격

# 인기 강의 정렬 기준 필드: DB 필드명과 일치할 것.
POPULAR_LECTURE_ORDER_BY: Final[str] = "-average_rating"

# 모델 관련 캐시 타임아웃 (TTL: Time To Live)
MODEL_CACHE_TIMEOUT: Final[int] = 60 * 60 * 24 * 7  # 7일
LECTURE_CATEGORY_MAP_TIMEOUT: Final[int] = 60 * 60 * 24  # 1일
LECTURE_METADATA_TTL: Final[int] = 60 * 60 * 6  # 6시간

# Redis 키 (버전 포함): 모델 버전이 변경되면 캐시를 무효화
ALS_MODEL_CACHE_KEY: Final[str] = f"als_model_{MODEL_VERSION}"
U_TO_IDX_CACHE_KEY: Final[str] = f"als_u_to_idx_{MODEL_VERSION}"
L_TO_IDX_CACHE_KEY: Final[str] = f"als_l_to_idx_{MODEL_VERSION}"
L_IDX_TO_ID_CACHE_KEY: Final[str] = f"als_l_idx_to_id_{MODEL_VERSION}"
USER_ITEMS_MATRIX_CACHE_KEY: Final[str] = f"als_user_items_matrix_{MODEL_VERSION}"
LECTURE_CATEGORY_MAP_CACHE_KEY: Final[str] = f"lecture_category_map_{MODEL_VERSION}"
# 강의별 메타데이터 캐시 키: 포맷팅 필요 (강의 ID를 위한 `{}`)
LECTURE_METADATA_CACHE_KEY: Final[str] = f"lecture_metadata_{MODEL_VERSION}:{{}}"

# 모델 로드/재캐싱 시 동시성 제어를 위한 Redis 락 키
ALS_TRAINING_LOCK_KEY: Final[str] = "als_training_lock"
