from django.db.models import TextChoices


class Provider(TextChoices):
    GOOGLE = "google", "Google"
    KAKAO = "kakao", "Kakao"
    NAVER = "naver", "Naver"


class Gender(TextChoices):
    MALE = "M", "남성"
    FEMALE = "F", "여성"


class Reason(TextChoices):
    NO_LONGER_NEEDED = "NO_LONGER_NEEDED", "서비스 이용할 시간이 없음"
    LACK_OF_INTEREST = "LACK_OF_INTEREST", "관심이 사라짐"
    TOO_DIFFICULT = "TOO_DIFFICULT", "서비스를 이용하기가 너무 어려움"
    FOUND_BETTER_SERVICE = "FOUND_BETTER_SERVICE", "더 좋은 대안을 찾음"
    PRIVACY_CONCERNS = "PRIVACY_CONCERNS", "개인정보/보안 우려"
    POOR_SERVICE_QUALITY = "POOR_SERVICE_QUALITY", "서비스 품질 불만"
    TECHNICAL_ISSUES = "TECHNICAL_ISSUES", "기술적 문제(버그 등)"
    LACK_OF_CONTENT = "LACK_OF_CONTENT", "원하는 콘텐츠나 기능의 부족"
    OTHER = "OTHER", "기타"


class VerificationPurpose(TextChoices):
    SIGNUP = "signup", "회원가입"
    ACCOUNT_RECOVERY = "account_recovery", "정보찾기"  # 아이디/비번 찾기
    PROFILE_UPDATE = "profile_update", "정보수정"  # 이메일/전화 변경
