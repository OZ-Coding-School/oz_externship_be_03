import os
from datetime import timedelta

import sentry_sdk

from config.settings.base import *

DEBUG = False
RAW_ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "")
if not RAW_ALLOWED_HOSTS:
    raise ValueError("DJANGO_ALLOWED_HOSTS must be set")
ALLOWED_HOSTS = RAW_ALLOWED_HOSTS.split(" ")

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

# jwt access token lifetime
SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"] = timedelta(minutes=60)
