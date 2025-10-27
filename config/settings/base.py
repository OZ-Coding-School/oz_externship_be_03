import os
from datetime import timedelta
from pathlib import Path
from typing import cast

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

if os.getenv("DJANGO_SETTINGS_MODULE") == "config.settings.local":
    load_dotenv(dotenv_path=BASE_DIR / "envs/.local.env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("DJANGO_SECRET_KEY environment variable not set")


# Application definition
DJANGO_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "debug_toolbar",
    "rest_framework_simplejwt",
    "rest_framework",
    "corsheaders",
    "drf_spectacular",
    "django_filters",
]

LOCAL_APPS = [
    "apps.core",
    "apps.users",
    "apps.lecture",
    "apps.notifications",
    "apps.recruitments",
    "apps.studies",
    "apps.chat",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "debug_toolbar.middleware.DebugToolbarMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST"),
        "PORT": os.getenv("DB_PORT"),
    }
}

for key, value in DATABASES.items():
    if key != "ENGINE":
        if not value:
            raise ValueError(f"Database {key} is empty")

# Redis Settings
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = os.getenv("REDIS_PORT")

if not REDIS_HOST or not REDIS_PORT:
    raise ValueError("REDIS_HOST and REDIS_PORT must be set")
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{REDIS_HOST}:{REDIS_PORT}/1",  # Redis 서버 주소
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(REDIS_HOST, REDIS_PORT)],
        },
    },
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# djangorestframework-simplejwt 관련 설정
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# Internationalization
LANGUAGE_CODE = "ko-KR"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# CORS Settings
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
CORS_ALLOW_HEADERS = [
    "accept",
    "authorization",
    "content-type",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]

# drf 관련 설정
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticatedOrReadOnly",),
    "DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework_simplejwt.authentication.JWTAuthentication",),
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 10,
}

# drf-spectacular 관련 설정
SPECTACULAR_SETTINGS = {
    "TITLE": "오즈 코딩 스쿨 Backend API",
    "DESCRIPTION": "오즈 코딩 스쿨의 웹 사이트 개발을 위한 API입니다.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SWAGGER_UI_SETTINGS": {
        "dom_id": "#swagger-ui",
        "layout": "BaseLayout",
        "deepLinking": True,  # API를 클릭할때 마다 SwaggerUI의 url이 변경됩니다. (특정 API url 공유시 유용하기때문에 True설정을 사용합니다)
        "persistAuthorization": True,  # True 이면 SwaggerUI상 Authorize에 입력된 정보가 새로고침을 하더라도 초기화되지 않습니다.
        "displayOperationId": True,  # True이면 API의 urlId 값을 노출합니다. 대체로 DRF api name둘과 일치하기때문에 api를 찾을때 유용합니다.
        "filter": True,  # True 이면 Swagger UI에서 'Filter by Tag' 검색이 가능합니다
    },
    "SERVE_PERMISSIONS": ["rest_framework.permissions.AllowAny"],
    "SECURITY": [
        {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        }
    ],
}

AUTH_USER_MODEL = "users.User"

# SMTP Settings
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", 587))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

# Twilio SMS Verify Settings
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "TWILIO_ACCOUNT_SID")
TWILIO_VERIFY_SERVICE_SID = os.environ.get("TWILIO_VERIFY_SERVICE_SID", "TWILIO_ACCOUNT_SID")

# Kakao OAuth Settings
KAKAO_CLIENT_ID = os.getenv("KAKAO_CLIENT_ID")
KAKAO_REDIRECT_URI = os.getenv("KAKAO_REDIRECT_URI")

# NAVER OAuth Settings
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")
NAVER_REDIRECT_URI = os.getenv("NAVER_REDIRECT_URI")

# AWS S3 settings
AWS_S3_REGION = os.getenv("AWS_S3_REGION", "")
AWS_S3_ACCESS_KEY_ID = os.getenv("AWS_S3_ACCESS_KEY_ID", "")
AWS_S3_SECRET_ACCESS_KEY = os.getenv("AWS_S3_SECRET_ACCESS_KEY", "")
AWS_S3_BUCKET_NAME = os.getenv("AWS_S3_BUCKET_NAME", "")

# Verify Flow 정책
ONE_TIME_TTL_SECONDS = 10 * 60  # 검증 토큰/대기 키 TTL (10분)
RESEND_COOLDOWN_SECONDS = 60  # 재전송 쿨다운 (60초)
ATTEMPT_LOCK_SECONDS = 10 * 60  # 실패 잠금 (10분)
MAX_FAIL_ATTEMPTS = 5

# Global Verify Flow 정책
GLOBAL_MAX_FAILS = 10
GLOBAL_LOCK_SECONDS = 3600

# 검증 토큰(JWT)
VERIFY_TOKEN_SECRET = os.getenv("VERIFY_TOKEN_SECRET", default=SECRET_KEY)
VERIFY_TOKEN_ALGO = "HS256"
VERIFY_TOKEN_EXPIRES_SECONDS = 10 * 60

# Celery 필수 설정
CELERY_BROKER_URL = f"redis://{REDIS_HOST}:6379/1"  # 환경에 맞게 수정
CELERY_RESULT_BACKEND = f"redis://{REDIS_HOST}:6379/2"  # 선택
CELERY_TIMEZONE = "Asia/Seoul"
CELERY_ENABLE_UTC = False

# 매일 00:10에 due_date 지난 유저 삭제
from celery.schedules import crontab  # type: ignore[import-untyped]

CELERY_BEAT_SCHEDULE = {
    "delete-withdrawn-users-daily": {
        "task": "apps.users.tasks.delete_withdrawn_users",
        "schedule": crontab(minute=10, hour=0),  # 매일 00:10 KST
        "options": {"expires": 60 * 60},  # 1시간 뒤 만료(중복 방지용)
        "args": (),
        "kwargs": {"batch_size": 1000},
    },
    # REQ-STDY-010: 스터디 그룹 상태 자동 업데이트
    "update-studygroup-status-daily": {
        "task": "apps.studies.tasks.update_studygroup_status_daily",
        "schedule": crontab(minute=1, hour=0),  # 매일 00:01 KST
        "options": {"expires": 60 * 60},
    },
}

# 리프레쉬 토큰 쿠키 설정
AUTH_REFRESH_COOKIE_NAME = "refresh_token"
AUTH_REFRESH_COOKIE_PATH = "/"
AUTH_REFRESH_COOKIE_MAX_AGE = int(cast(timedelta, SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"]).total_seconds())
AUTH_REFRESH_COOKIE_SECURE = True
AUTH_REFRESH_COOKIE_HTTPONLY = True
AUTH_REFRESH_COOKIE_SAMESITE = "None"
