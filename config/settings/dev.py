import os

import sentry_sdk

from config.settings.base import *

DEBUG = True
RAW_ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "")
if not RAW_ALLOWED_HOSTS:
    raise ValueError("DJANGO_ALLOWED_HOSTS must be set")
ALLOWED_HOSTS = RAW_ALLOWED_HOSTS.split(" ")

# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

INTERNAL_IPS = [
    "127.0.0.1",
]

# cors & csrf settings
CORS_ALLOWED_ORIGINS = os.getenv("CORS_ALLOWED_ORIGINS", "").split(" ")
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

# sentry logging settings
SENTRY_DSN = os.getenv("SENTRY_DSN")
if not SENTRY_DSN:
    raise ValueError("SENTRY_DSN must be set. For Error Logging")
sentry_sdk.init(
    dsn=SENTRY_DSN,
    traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", 1)),
    profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", 1)),
)

# logging settings
LOG_ROOT = os.path.join(BASE_DIR, "logs")
if not os.path.exists(LOG_ROOT):
    os.makedirs(LOG_ROOT)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "require_debug_true": {"()": "django.utils.log.RequireDebugTrue"},
    },
    "formatters": {
        "simple": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "django.server": {
            "()": "django.utils.log.ServerFormatter",
            "format": "[{server_time}] {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "filters": ["require_debug_true"],
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(LOG_ROOT, "django.log"),
            "formatter": "simple",
            "maxBytes": 1024 * 1024 * 5,
            "backupCount": 10,
        },
        "django.server": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "django.server",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
        },
        "django.server": {
            "handlers": ["django.server"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
