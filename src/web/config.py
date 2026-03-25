# src/web/config.py

from shared.env import env_bool, env_list, env_str, get_int_env

APP_NAME = env_str("APP_NAME", default="Suite")
APP_VERSION = env_str("APP_VERSION", default="1.0")
LOGIN_MODE = env_str("LOGIN_MODE", default="dev")
SECRET = env_str("SECRET")
DEV = env_bool("DEV", default=True)
PORT = get_int_env("PORT", default=8050)
CLIENT_ID = env_str("CLIENT_ID", default="")
CLIENT_SECRET = env_str("CLIENT_SECRET", default="")
TENANT_ID = env_str("TENANT_ID", default="common")
AUTHORITY = env_str("AUTHORITY", default=f"https://login.microsoftonline.com/{TENANT_ID}")
SCOPE = env_list("SCOPE", default="")
REDIRECT_URI = env_str("REDIRECT_URI", default=f"http://localhost:{PORT}/getAToken")
REDIRECT_PATH = env_str("REDIRECT_PATH", default="/getAToken")
CELERY_BROKER_URL = env_str("CELERY_BROKER_URL", default="redis://redis:6379/0")
MAX_USER_TASKS_ACTIVE = get_int_env("MAX_USER_TASKS_ACTIVE", default=3, amin=1)
MAX_USER_TASKS_TOTAL = get_int_env("MAX_USER_TASKS_TOTAL", default=50, amin=1)
