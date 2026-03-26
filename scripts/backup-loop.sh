#!/bin/sh
set -eu

BACKUP_DIR="/backups"
INTERVAL="${BACKUP_INTERVAL_SECONDS:-86400}"
DB_HOST="${POSTGRES_HOST:-postgres}"
DB_USER="${POSTGRES_USER:-postgres}"
DB_NAME="${POSTGRES_DB:-appdb}"

log() {
  echo "[$(date -Iseconds)] $*"
}

while true; do
  ts="$(date +%Y%m%d)"
  file="${BACKUP_DIR}/postgres_${ts}.dump"

  start=$(date +%s)

  log "starting backup → ${file}"

  if pg_dump \
    --format=custom \
    --no-owner \
    --no-privileges \
    -h "${DB_HOST}" \
    -U "${DB_USER}" \
    "${DB_NAME}" > "${file}"
  then
    end=$(date +%s)
    duration=$((end - start))

    size_bytes=$(wc -c < "$file")
    size_human=$(du -h "$file" | cut -f1)

    log "backup SUCCESS → ${file} (${size_human}, ${size_bytes} bytes) in ${duration}s"
  else
    end=$(date +%s)
    duration=$((end - start))

    log "backup FAILED after ${duration}s"
  fi

  log "next backup in ${INTERVAL}s"
  sleep "${INTERVAL}"

done