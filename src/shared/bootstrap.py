from shared.db import init_db
from shared.logs import init_logs


def bootstrap() -> None:
    init_logs()
    init_db()
