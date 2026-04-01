docker compose up --build  (run locally)
docker compose --profile test run --rm test  (unit tests)
winget install Microsoft.AzureCLI  (installs)
docker compose run --rm web alembic revision --autogenerate -m "initial schema"  (generate initial schema alembic)
