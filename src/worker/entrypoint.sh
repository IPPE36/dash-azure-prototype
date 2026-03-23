#!/usr/bin/env sh
set -eu

APP="shared.celery_app:celery_app"
QUEUE="${WORKER_QUEUE:-default}"
NAME="${WORKER_NAME:-worker@%h}"
LOGLEVEL="${WORKER_LOGLEVEL:-INFO}"
CONCURRENCY="${WORKER_CONCURRENCY:-1}"

exec celery -A "$APP" worker \
  --loglevel="$LOGLEVEL" \
  -Q "$QUEUE" \
  --concurrency="$CONCURRENCY" \
  -n "$NAME"
