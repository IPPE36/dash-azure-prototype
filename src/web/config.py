# src/web/config.py

from shared.env import env_bool, env_list, env_str, get_int_env

APP_NAME = env_str("APP_NAME", "Suite")
APP_VERSION = env_str("APP_VERSION", "1.0")
DEV = env_bool("DEV", default=True)
CLIENT_ID = env_str("CLIENT_ID", "")
CLIENT_SECRET = env_str("CLIENT_SECRET", "")
TENANT_ID = env_str("TENANT_ID", "common")
AUTHORITY = env_str("AUTHORITY", f"https://login.microsoftonline.com/{TENANT_ID}")
SECRET = env_str("SECRET", "fallback-secret")
SCOPE = env_list("SCOPE", "")
REDIRECT_URI = env_str("REDIRECT_URI", "")
REDIRECT_PATH = env_str("REDIRECT_PATH", "/getAToken")
CELERY_BROKER_URL = env_str("CELERY_BROKER_URL", "")
MAX_USER_TASKS_ACTIVE = get_int_env("MAX_USER_TASKS_ACTIVE", default=3, amin=1)
MAX_USER_TASKS_TOTAL = get_int_env("MAX_USER_TASKS_TOTAL", default=50, amin=1)
