https://bootstrap.build/app
docker compose up --build  (run locally)
docker compose --profile test run --rm test  (run unit tests)
winget install Microsoft.AzureCLI  (installs azure cli)
docker compose run --rm web alembic revision --autogenerate -m "initial schema"  (generate initial schema for alembic)
