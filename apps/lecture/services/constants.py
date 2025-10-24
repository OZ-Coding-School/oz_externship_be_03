from dataclasses import dataclass
from typing import Dict, Final

# 사용자 상호작용 가중치 (불변 딕셔너리)
INTERACTION_WEIGHTS: Final[Dict[str, float]] = {
    "bookmark": 3.0,  # 북마크: 가장 강한 긍정 신호
    "search": 1.0,  # 검색: 낮은 강도의 관심 표현
    "study_participation": 2.0,  # 스터디 참여: 높은 몰입 신호
    "category_match": 2.5,  # 카테고리 일치: 장기 선호도 반영
    "review_rating": 1.5,  # 리뷰 평점: 품질 만족도 반영
}

# 문자열 평점 → 숫자 매핑 (불변 딕셔너리)
RATING_SCORE_MAP: Final[Dict[str, float]] = {
    "5_OUT_OF_5_STARS": 5.0,
    "4_OUT_OF_5_STARS": 4.0,
    "3_OUT_OF_5_STARS": 3.0,
    "2_OUT_OF_5_STARS": 2.0,
    "1_OUT_OF_5_STARS": 1.0,
}

# 검색 상호작용 선별적 반영을 위한 상수
SEARCH_LOG_DAYS_LIMIT: Final[int] = 30  # 최근 30일 이내 검색 로그만 사용

# 인기 강의 정렬 기준 필드 (Django ORM 필드 이름)
POPULAR_LECTURE_ORDER_BY: Final[str] = "-average_rating"

# ALS 모델 캐시 관련 상수
MODEL_CACHE_TIMEOUT: Final[int] = 60 * 60 * 24 * 7  # 7일 (604800초)
ALS_MODEL_CACHE_KEY: Final[str] = "als_model_v1"
U_TO_IDX_CACHE_KEY: Final[str] = "als_u_to_idx_v1"
L_TO_IDX_CACHE_KEY: Final[str] = "als_l_to_idx_v1"
L_IDX_TO_ID_CACHE_KEY: Final[str] = "als_l_idx_to_id_v1"
USER_ITEMS_MATRIX_CACHE_KEY: Final[str] = "als_user_items_matrix_v1"

# Redis 캐시 설정 상수
LECTURE_CATEGORY_MAP_CACHE_KEY: Final[str] = "lecture_category_map_v1"
LECTURE_CATEGORY_MAP_TIMEOUT: Final[int] = 60 * 60 * 24  # 1일 (86400초)


# ALS 하이퍼파라미터 (dataclass + 불변)
@dataclass(frozen=True)
class ALS_Hyperparameters:
    factors: int = 50  # 잠재 요인(Latent Factors)의 수
    regularization: float = 0.1  # 정규화 강도
    iterations: int = 15  # 반복 횟수
    calculate_training_loss: bool = False  # 훈련 손실 계산 여부 (성능 최적화를 위해 False)
    use_gpu: bool = False  # GPU 사용 여부


ALS_PARAMS: Final[ALS_Hyperparameters] = ALS_Hyperparameters()
