#!/bin/sh
set -e

echo "[entrypoint] Running DB bootstrap..."
python -m shared.db.bootstrap

echo "[entrypoint] Starting application..."
exec "$@"