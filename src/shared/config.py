# src/shared/config.py

from shared.env import env_bool, env_str, get_int_env

APP_VERSION = env_str("APP_VERSION", "1.0")
CELERY_BROKER_URL = env_str("CELERY_BROKER_URL", "")
CELERY_RESULT_BACKEND = env_str("CELERY_RESULT_BACKEND", "")
LOG_LEVEL = env_str("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = env_str("LOG_FORMAT", "console").lower()
DEV = env_bool("DEV", default=True)
DATABASE_URL = env_str("DATABASE_URL", "")
DB_BACKUP_ON_STARTUP = env_bool("DB_BACKUP_ON_STARTUP", default=True)
DB_BACKUP_DIR = env_str("DB_BACKUP_DIR", "./db_backups") or "./db_backups"
DB_BACKUP_MAX_AGE_HOURS = get_int_env("DB_BACKUP_MAX_AGE_HOURS", default=168, amin=1)
INIT_DB_ON_WORKER = env_bool("INIT_DB_ON_WORKER", default=False)
