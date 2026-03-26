# src/shared/db/bootstrap.py

from shared.log import configure_logs
from shared.db import configure_db

def main() -> None:
    configure_logs()
    configure_db()

if __name__ == "__main__":
    main()