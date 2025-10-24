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


# ALS 하이퍼파라미터 (dataclass + 불변)
@dataclass(frozen=True)
class ALS_Hyperparameters:
    factors: int = 50  # 잠재 요인(Latent Factors)의 수
    regularization: float = 0.1  # 정규화 강도
    iterations: int = 15  # 반복 횟수
    calculate_training_loss: bool = False  # 훈련 손실 계산 여부 (성능 최적화를 위해 False)
    use_gpu: bool = False  # GPU 사용 여부


ALS_PARAMS: Final[ALS_Hyperparameters] = ALS_Hyperparameters()
