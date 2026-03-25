# src/shared/config.py

from shared.env import env_bool, env_str

DATABASE_URL = env_str("DATABASE_URL")
DEV = env_bool("DEV", default=True)
AUTH_MODE = env_str("AUTH_MODE", default="dev")
APP_VERSION = env_str("APP_VERSION", default="1.0")
CELERY_BROKER_URL = env_str("CELERY_BROKER_URL", default="redis://redis:6379/0")
CELERY_RESULT_BACKEND = env_str("CELERY_RESULT_BACKEND", default="redis://redis:6379/0")
LOG_LEVEL = env_str("LOG_LEVEL", default="INFO").upper()
LOG_FORMAT = env_str("LOG_FORMAT", default="console")