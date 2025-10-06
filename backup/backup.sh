#!/usr/bin/env bash
set -euo pipefail

DST="${BACKUP_DIR:-/backups}"
INTERVAL="${BACKUP_INTERVAL_SECONDS:-86400}"
KEEP="${BACKUP_KEEP_COUNT:-7}"

mkdir -p "$DST"

log() { printf '[backup] %s\n' "$*"; }

while true; do
  TS=$(date +'%Y%m%d_%H%M%S')
  OUT="$DST/finance_${TS}.dump"

  log "starting pg_dump -> $OUT"
  # Custom format (-Fc), compressed (-Z 9) on pg16; fastest safe dump
  PGPASSWORD="${POSTGRES_PASSWORD:?}" pg_dump \
    -h "${POSTGRES_HOST:?}" -p "${POSTGRES_PORT:?}" \
    -U "${POSTGRES_USER:?}" -d "${POSTGRES_DB:?}" \
    -F c -Z 9 -f "$OUT"

  # Quick integrity check: list archive contents
  if ! PGPASSWORD="${POSTGRES_PASSWORD:?}" pg_restore -l "$OUT" >/dev/null; then
    log "pg_restore failed; removing corrupt dump $OUT"
    rm -f "$OUT"
  else
    log "dump complete: $OUT"
  fi

  # Rotation: keep newest $KEEP, delete the rest
  log "rotating to keep last $KEEP dumps"
  ls -1t "$DST"/finance_*.dump 2>/dev/null | tail -n +$((KEEP+1)) | xargs -r rm -f || true

  log "sleeping ${INTERVAL}s"
  sleep "$INTERVAL"
done
