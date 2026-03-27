#!/bin/sh
set -eu

BACKUP_DIR="/backups/dumps"
INTERVAL="${BACKUP_INTERVAL_SECONDS:-86400}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-180}"
DB_HOST="${POSTGRES_HOST:-postgres}"
DB_USER="${POSTGRES_USER:-postgres}"
DB_NAME="${POSTGRES_DB:-appdb}"

log() {
  echo "[$(date -Iseconds)] $*"
}

while true; do
  ts="$(date +%Y%m%d_%H%M%S)"
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
    log "pruning backups older than ${RETENTION_DAYS} days"
    find "${BACKUP_DIR}" -type f -name "postgres_*.dump" -mtime +"${RETENTION_DAYS}" -print -delete
  else
    end=$(date +%s)
    duration=$((end - start))

    log "backup FAILED after ${duration}s"
  fi

  log "next backup in ${INTERVAL}s"
  sleep "${INTERVAL}"

done
