#!/bin/sh
set -e

if [ "$RUN_MIGRATIONS" = "true" ]; then
  echo "[entrypoint] RUN_MIGRATIONS=true -> running migrations..."
  python -m shared.db.migrations
fi

echo "[entrypoint] running DB bootstrap..."
python -m shared.db.bootstrap

echo "[entrypoint] starting application..."
exec "$@"