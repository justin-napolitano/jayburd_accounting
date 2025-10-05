#!/usr/bin/env bash
set -euo pipefail

echo "[bootstrap] waiting for db ${POSTGRES_HOST:-db}:${POSTGRES_PORT:-5432}"
for i in {1..60}; do
  if pg_isready -h "${POSTGRES_HOST:-db}" -p "${POSTGRES_PORT:-5432}" -U "${POSTGRES_USER:?}" -d "${POSTGRES_DB:?}" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

export PGPASSWORD="${POSTGRES_PASSWORD:?}"

echo "[bootstrap] applying admin roles/grants"
psql -v ON_ERROR_STOP=1 -h "${POSTGRES_HOST:-db}" -p "${POSTGRES_PORT:-5432}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -f /app/db/admin/roles.sql

echo "[bootstrap] ensuring schema_migrations table"
psql -v ON_ERROR_STOP=1 -h "${POSTGRES_HOST:-db}" -p "${POSTGRES_PORT:-5432}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -f /app/db/migrations/0000_schema_migrations.sql

echo "[bootstrap] running migrations"
shopt -s nullglob
for f in /app/db/migrations/*.sql; do
  base="$(basename "$f")"
  # skip the tracker file; it was already applied above
  if [[ "$base" == "0000_schema_migrations.sql" ]]; then
    continue
  fi
  applied=$(psql -t -A -h "${POSTGRES_HOST:-db}" -p "${POSTGRES_PORT:-5432}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" \
    -c "select 1 from schema_migrations where version = '$base'")
  if [[ "$applied" != "1" ]]; then
    echo "[bootstrap] applying $base"
    psql -v ON_ERROR_STOP=1 -h "${POSTGRES_HOST:-db}" -p "${POSTGRES_PORT:-5432}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -f "$f"
    psql -v ON_ERROR_STOP=1 -h "${POSTGRES_HOST:-db}" -p "${POSTGRES_PORT:-5432}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" \
      -c "insert into schema_migrations(version) values ('$base')"
  else
    echo "[bootstrap] already applied $base"
  fi
done

echo "[bootstrap] done"
