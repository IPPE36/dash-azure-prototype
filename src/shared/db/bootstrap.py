# src/shared/db/bootstrap.py

def main() -> None:
    from shared.log import configure_logs
    configure_logs()
    from shared.db import configure_db
    configure_db()

if __name__ == "__main__":
    main()