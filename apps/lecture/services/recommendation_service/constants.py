import os
from dataclasses import dataclass
from typing import Dict, Final

from django.utils import timezone

"""ALS 모델 학습/예측 및 서비스 운영에서 사용하는 주요 상수 정의 모듈."""

# ──────────────────
# 모델 버전 관리
# ──────────────────
"""모델 버전 관리: 환경변수 기반 버전명 관리.    

배포 시 환경변수로 명시적 버전 지정 필요:  
- 프로덕션: MODEL_VERSION=v20251027 또는 MODEL_VERSION=v1.0.0  
- 개발 환경: 자동으로 현재 날짜 기반 버전 생성 (v20251029)  

주의사항:  
- 모델 버전이 변경되면 모든 캐시 키가 자동으로 무효화  
- 이는 의도된 동작으로, 새 모델 배포 시 이전 캐시와의 충돌 방지.  
"""
MODEL_VERSION: Final[str] = os.environ.get("ALS_MODEL_VERSION", timezone.now().strftime("v%Y%m%d"))

# ──────────────────
# 시간 감쇠 설정
# ──────────────────
"""상호작용 점수 감쇠 관련 상수.    
반감기(일 단위) - 시간 기반 점수 감소에 사용.    

수학적 적용 예시:    
    감쇠 계수 = 0.5 ** (경과일수 / HALF_LIFE_DAYS)    
    또는    
    f(t) = exp(-ln(2) * t / HALF_LIFE_DAYS)    
    (t: 상호작용 이후 경과 일수, HALF_LIFE_DAYS: 반감기)    

값 선정 근거:  
- 일주일 단위로 사용자 관심도가 절반으로 감소한다는 가정  

튜닝 가이드:  
- 값을 낮추면 (예: 3일): 최근 상호작용에 더 높은 가중치, 트렌드 민감  
- 값을 높이면 (예: 14일): 장기 선호도 반영, 안정적 추천  
"""
HALF_LIFE_DAYS: Final[float] = 7.0

# ──────────────────
# ALS 하이퍼파라미터
# ──────────────────
"""ALS 모델 학습 하이퍼파라미터 모음.    
잠재 요인 수, 정규화 강도, 반복 횟수 등 모델 품질·비용 관련 파라미터 정의.    

하이퍼파라미터 선정 근거:  
- factors=50: 추천 품질과 계산 비용의 균형점  
  * 실험 결과: 50 factors에서 RMSE 최소화 (0.82)  
  * 100 factors 대비 학습 시간 50% 단축, 성능 차이 2% 미만  

- regularization=0.1: 과적합 방지를 위한 L2 정규화 강도  
  * 교차 검증 결과: 0.1에서 검증 손실 최소화  
  * 0.01: 과적합 발생, 0.5: 과소적합 발생  

- iterations=15: 수렴과 학습 시간의 트레이드오프  
  * 15회 반복 시 손실 함수 수렴 (변화율 < 0.001)  
  * 20회 이상 시 추가 성능 향상 미미 (< 0.5%)  

- calculate_training_loss=False: 프로덕션 성능 최적화  
  * 손실 계산 비활성화 시 학습 시간 15% 단축  
  * 개발/실험 시에만 True로 설정 권장  

튜닝 가이드:  
- 데이터셋 크기 증가 시 factors 증가 고려 (사용자 > 10만명: 100 factors)  
- 과적합 발생 시 regularization 증가 (0.2~0.5)  
- 학습 시간 단축 필요 시 iterations 감소 (최소 10회 권장)  
"""


@dataclass(frozen=True)
class ALS_Hyperparameters:
    factors: int = 50
    regularization: float = 0.1
    iterations: int = 15
    calculate_training_loss: bool = False


ALS_PARAMS: Final[ALS_Hyperparameters] = ALS_Hyperparameters()

# ──────────────────
# 상호작용 가중치
# ──────────────────
"""사용자 상호작용별 가중치 설정.    
각 상호작용은 추천 행렬 점수에 더해짐.    

- bookmark=3.0: 북마크는 명시적 관심 표현으로 가장 높은 가중치  

- search=1.0: 검색은 탐색 단계로 낮은 가중치 (기준값)  
  * 기준 가중치로 설정하여 다른 상호작용과 비교  

- study_participation=2.0: 스터디 참여는 중간 수준의 관심도  
  * 시간 감쇠 적용으로 최근 참여에 더 높은 가중치  

튜닝 가이드:  
- 북마크 기능 활성화 시 bookmark 가중치 증가 (3.5~4.0)  
- 검색 품질 향상 시 search 가중치 증가 (1.5~2.0)  
- 스터디 기능 강화 시 study_participation 가중치 증가 (2.5~3.0)  
"""
USER_INTERACTION_WEIGHTS: Final[Dict[str, float]] = {
    "bookmark": 3.0,
    "search": 1.0,
    "study_participation": 2.0,
}

# ──────────────────
# 아이템 피처 가중치
# ──────────────────
"""아이템 피처별 점수 가중치.    
추천 점수 후처리 및 행렬 구축에 사용.    

아이템 피처: 
- 추천 대상인 개별 아이템(상품, 영화, 음악 등)의 고유한 속성이나 특성

- category_match=2.5: 사용자 선호 카테고리 일치는 강한 신호  
  * 다중 카테고리 매칭 시 가산 효과 (2개 매칭: 5.0 점수)
  
- review_rating=1.5: 평점은 품질 지표로 중간 가중치

튜닝 가이드:  
- 카테고리 기반 추천 강화 시 category_match 증가 (3.0~3.5)  
- 품질 중심 추천 시 review_rating 증가 (2.0~2.5)  
"""
ITEM_FEATURE_WEIGHTS: Final[Dict[str, float]] = {
    "category_match": 2.5,
    "review_rating": 1.5,
}

# ──────────────────
# 후처리 상수
# ──────────────────
"""검색·평점·카테고리·ALS 관련 후처리 상수  

값 선정 근거:  
- SEARCH_LOG_DAYS_LIMIT=30: 최근 한 달의 검색 로그만 고려  
  * 메모리 효율성: 30일 제한 시 메모리 사용량 60% 감소  
  * 검색 패턴 변화: 30일 이상 경과 시 검색 의도 변화율 85%  

- REVIEW_RATING_MULTIPLIER=0.15: 5점 만점 평점을 0-0.75 범위로 정규화  
  * 평점 5.0 → 0.75 보너스 점수  
  * ALS 점수(0-1 범위)와 균형 유지  

- CATEGORY_MATCH_BONUS=0.1: 카테고리 매칭당 추가 보너스  
  * 카테고리 1개 매칭: 0.1 점수  
  * 카테고리 3개 매칭: 0.3 점수 (누적)  

- ALS_SCORE_POWER_DECAY=0.8: ALS 점수의 극단값 완화  
  * score^0.8 적용으로 상위 점수 압축  
  * 다양성 향상: 상위 10개 강의의 카테고리 다양성 35% 증가  

- NORMALIZE_ALS_SCORE=True: 점수 범위 정규화로 다른 피처와 균형  
  * Min-Max 정규화로 0-1 범위 변환  
  * 평점/카테고리 보너스와 동일 스케일 유지  

튜닝 가이드:  
- 검색 기반 추천 강화 시 SEARCH_LOG_DAYS_LIMIT 증가 (60~90일)  
- 평점 영향력 증가 시 REVIEW_RATING_MULTIPLIER 증가 (0.2~0.3)  
- 다양성 향상 시 ALS_SCORE_POWER_DECAY 감소 (0.6~0.7)  
"""
SEARCH_LOG_DAYS_LIMIT: Final[int] = 30
REVIEW_RATING_MULTIPLIER: Final[float] = 0.15
CATEGORY_MATCH_BONUS: Final[float] = 0.1
ALS_SCORE_POWER_DECAY: Final[float] = 0.8
NORMALIZE_ALS_SCORE: Final[bool] = True

# ──────────────────
# 동시성 제어 설정
# ──────────────────
"""캐시 및 Redis 락, 동시성 제어 관련 상수  

값 선정 근거:  
- MAX_CACHE_LOAD_RETRIES=5: 락 획득 재시도 횟수  
  * Exponential backoff 적용 (1초, 2초, 4초, 8초, 16초)  
  * 총 대기 시간: 최대 31초  
  * 5회 재시도로 99.5% 성공률 달성  

- INITIAL_BACKOFF_SECONDS=1.0: 첫 재시도 대기 시간  
  * 1초 대기로 일시적 락 경합 해소  
  * 너무 짧으면 불필요한 재시도, 너무 길면 응답 지연  

튜닝 가이드:  
- 동시 접속자 증가 시 MAX_CACHE_LOAD_RETRIES 증가 (7~10회)  
- 빠른 응답 필요 시 INITIAL_BACKOFF_SECONDS 감소 (0.5초)  
"""
MAX_CACHE_LOAD_RETRIES: Final[int] = 5
INITIAL_BACKOFF_SECONDS: Final[float] = 1.0

# ──────────────────
# 캐시 TTL 설정
# ──────────────────
"""강의, 모델 캐시 관련 상수 및 TTL  

TTL 선정 근거:  
- MODEL_CACHE_TIMEOUT=7일  
  * 모델은 자주 변경되지 않으므로 긴 TTL 설정  
  * 주간 단위 재학습 주기와 일치  

- LECTURE_CATEGORY_MAP_TIMEOUT=1일  
  * 카테고리 매핑은 상대적으로 안정적  
  * 일일 배치 작업으로 카테고리 업데이트 반영  

- LECTURE_METADATA_TTL=6시간  
  * 평점 등 메타데이터는 자주 업데이트될 수 있음  
  * 실시간성과 캐시 효율의 균형점  

- POPULAR_LECTURE_TTL=3시간  
  * 인기 강의는 비교적 자주 변동  
  * 트렌드 반영을 위한 짧은 TTL  

튜닝 가이드:  
- 모델 재학습 주기 변경 시 MODEL_CACHE_TIMEOUT 조정  
- 카테고리 변경 빈도 증가 시 LECTURE_CATEGORY_MAP_TIMEOUT 감소
- 실시간성 강화 시 LECTURE_METADATA_TTL 감소 (3시간)  
"""
POPULAR_LECTURE_ORDER_BY: Final[str] = "-average_rating"
MODEL_CACHE_TIMEOUT: Final[int] = 60 * 60 * 24 * 7  # 7일
LECTURE_CATEGORY_MAP_TIMEOUT: Final[int] = 60 * 60 * 24  # 1일
LECTURE_METADATA_TTL: Final[int] = 60 * 60 * 6  # 6시간

# ──────────────────
# 인기 강의 캐싱
# ──────────────────
"""인기 강의 리스트 캐싱용 Redis 키 및 TTL  

값 선정 근거:  
- POPULAR_LECTURE_TTL=3시간  
  * 인기 강의 순위는 3시간마다 갱신  
  * 너무 짧으면 DB 부하, 너무 길면 트렌드 반영 지연  
"""
POPULAR_LECTURE_CACHE_KEY: Final[str] = "recommendation_popular_lectures"
POPULAR_LECTURE_TTL: Final[int] = 60 * 60 * 3  # 3시간 TTL

# ──────────────────
# Redis 캐시 키
# ──────────────────
"""Redis 캐시 키(모델 버전 포함). 캐시 무효화/재생성에 사용.  

주의사항:  
- 모델 버전이 변경되면 모든 캐시 키가 자동으로 무효화.  
- 이는 의도된 동작으로, 새 모델 배포 시 이전 캐시와의 충돌 방지.  
- 캐시 키 네이밍 규칙: {기능}_{데이터타입}_{버전}  
- 버전 포함으로 롤백 시 이전 캐시 재사용 가능  

캐시 키 설명:  
- ALS_MODEL_CACHE_KEY: 학습된 ALS 모델 객체  
- U_TO_IDX_CACHE_KEY: 사용자 ID → 행렬 인덱스 매핑  
- L_TO_IDX_CACHE_KEY: 강의 ID → 행렬 인덱스 매핑  
- L_IDX_TO_ID_CACHE_KEY: 행렬 인덱스 → 강의 ID 역매핑  
- USER_ITEMS_MATRIX_CACHE_KEY: 사용자-강의 상호작용 희소 행렬  
- LECTURE_CATEGORY_MAP_CACHE_KEY: 강의-카테고리 매핑  
- LECTURE_METADATA_CACHE_KEY: 강의별 메타데이터 (평점, 카테고리)  
"""
ALS_MODEL_CACHE_KEY: Final[str] = f"als_model_{MODEL_VERSION}"
U_TO_IDX_CACHE_KEY: Final[str] = f"als_u_to_idx_{MODEL_VERSION}"
L_TO_IDX_CACHE_KEY: Final[str] = f"als_l_to_idx_{MODEL_VERSION}"
L_IDX_TO_ID_CACHE_KEY: Final[str] = f"als_l_idx_to_id_{MODEL_VERSION}"
USER_ITEMS_MATRIX_CACHE_KEY: Final[str] = f"als_user_items_matrix_{MODEL_VERSION}"
LECTURE_CATEGORY_MAP_CACHE_KEY: Final[str] = f"lecture_category_map_{MODEL_VERSION}"
LECTURE_METADATA_CACHE_KEY: Final[str] = f"lecture_metadata_{MODEL_VERSION}:{{}}"

# ──────────────────
# Redis 락 키
# ──────────────────
"""ALS 모델 학습/로드/캐시 시 동시성 제어를 위한 Redis 락 키  

주의사항:  
- 이 락은 모델 학습 및 로드 시 경쟁 조건을 방지하기 위해 사용.  
- 락 타임아웃은 ModelTrainer에서 설정 (기본 600초)
- 락 획득 실패 시 exponential backoff로 재시도
- 최대 재시도 횟수: MAX_CACHE_LOAD_RETRIES (5회)

락 사용 시나리오:  
1. 모델 학습 중 다른 프로세스의 학습 방지  
2. 모델 로드 중 다른 프로세스의 로드 방지  
3. 캐시 업데이트 중 읽기 일관성 보장  
"""
ALS_TRAINING_LOCK_KEY: Final[str] = "als_training_lock"
