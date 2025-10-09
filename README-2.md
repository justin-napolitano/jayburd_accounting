# Finance OS (Headless) — Docker Build & Sanity Guide

This README documents how to build, run, and sanity-check each service in the headless finance stack. It assumes you’re running Docker Compose locally and using CSV/OFX email ingestion first, with a clean path to add Plaid later.

---

## Contents
- [Prerequisites](#prerequisites)
- [Environment (.env)](#environment-env)
- [First-time Initialization](#first-time-initialization)
- [Service Matrix](#service-matrix)
- [Build, Run, and Sanity Checks](#build-run-and-sanity-checks)
  - [Database (db)](#1-database-db)
  - [Bootstrap (db-bootstrap)](#2-bootstrap-db-bootstrap)
  - [Email Ingestor (ingestor-email)](#3-email-ingestor-ingestor-email)
  - [Normalizer (normalizer)](#4-normalizer-normalizer)
  - [Classifier (classifier)](#5-classifier-classifier)
  - [Budget Importer (budgeter)](#6-budget-importer-budgeter)
  - [Read-only API (api)](#7-read-only-api-api)
  - [Scheduler (scheduler)](#8-scheduler-scheduler)
  - [Backups (backup)](#9-backups-backup)
  - [Teller Enroll (teller-enroll)](#10-teller-enroll-teller-enroll)
  - [Teller Sync (teller-sync)](#11-teller-sync-teller-sync)
- [Suggested Run Order](#suggested-run-order)
- [Troubleshooting](#troubleshooting)
- [Cloud Notes](#cloud-notes)

---

## Prerequisites

- **Docker & Docker Compose** installed and running (rootless Docker is fine).
- A **`.env`** file at repo root (see below).
- **psql** client for DB checks (optional but useful).
- **curl** (and optionally **jq**) for API checks.

> Host port mappings used here:
> - Postgres exposed at **localhost:5434** → container 5432
> - API exposed at **localhost:8010** → container 8000

---

## Environment (.env)

Create a `.env` in the repository root. Example:

```dotenv
# DB
POSTGRES_DB=finance
POSTGRES_USER=fin_writer
POSTGRES_PASSWORD=change_me_now
POSTGRES_READONLY_USER=fin_reader
POSTGRES_READONLY_PASSWORD=read_only_please
POSTGRES_HOST=db
POSTGRES_PORT=5432
TZ=America/New_York

# Scheduler (host specifics — adjust for your machine)
HOST_WORKSPACE=/absolute/path/to/your/repo
DOCKER_SOCK_PATH=/run/user/1000/docker.sock
COMPOSE_PROJECT_NAME=finance

# IMAP (for ingestor-email)
IMAP_HOST=imap.gmail.com
IMAP_USER=finance.imports.yourname@gmail.com
IMAP_PASS=your_app_password_here
IMAP_FOLDER=bank-export
RAW_DIR=/data/raw
BANK_NAME=

# Teller (mTLS + Basic)
TELLER_BASE_URL=https://api.teller.io
TELLER_AUTH_STYLE=basic
TELLER_ENROLLMENT_ID=usr_pjhb69paqhfgdf39js000
TELLER_ACCESS_TOKEN=token_4yobfknid5ho4chpxo2drtcz3q

# Mounted inside containers by docker-compose
TELLER_CERT_PATH=/secrets/teller/certificate.pem
TELLER_KEY_PATH=/secrets/teller/private_key.pem

# enroll/sync window
TELLER_SINCE_DAYS=30
```

Security hygiene on host:
```bash
chmod 0400 ./secrets/teller/private_key.pem
chmod 0444 ./secrets/teller/certificate.pem
```

---

## First-time Initialization

1) **Start Postgres**  
```bash
docker compose up -d db
```

2) **Run bootstrap** (roles, grants, migrations; safe to re-run)  
```bash
docker compose up --no-deps db-bootstrap
```

3) **Verify**  
```bash
# Extensions
PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -p 5434 -U $POSTGRES_USER -d $POSTGRES_DB -c '\dx'

# Migrations tracker
PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -p 5434 -U $POSTGRES_USER -d $POSTGRES_DB -c 'table schema_migrations;'
```

---

## Service Matrix

| Service          | Path               | Build                                      | Run                                              | Purpose |
|------------------|--------------------|--------------------------------------------|--------------------------------------------------|---------|
| `db`             | `db/`              | n/a (official image)                       | `docker compose up -d db`                        | Postgres with extensions |
| `db-bootstrap`   | `ops/scripts/`     | n/a (official image)                       | `docker compose up --no-deps db-bootstrap`       | Idempotent roles + migrations |
| `ingestor-email` | `ingestor-email/`  | `docker compose build ingestor-email`      | `docker compose run --rm ingestor-email`         | Pull email attachments (CSV/OFX/QFX) |
| `normalizer`     | `normalizer/`      | `docker compose build normalizer`          | `docker compose run --rm normalizer`             | Normalize raw files to `transactions` |
| `classifier`     | `classifier/`      | `docker compose build classifier`          | `docker compose run --rm classifier`             | Apply keyword rules → `tx_splits` |
| `budgeter`       | `budgeter/`        | `docker compose build budgeter`            | `docker compose run --rm budgeter`               | Import monthly budgets from YAML |
| `api`            | `api/`             | `docker compose build api`                 | `docker compose up -d api`                       | Read-only HTTP API (port 8010) |
| `scheduler`      | `scheduler/`       | `docker compose build scheduler`           | `docker compose up -d scheduler`                 | Cron-like orchestration of jobs |
| `backup`         | `backup/`          | `docker compose build backup`              | `docker compose up -d backup`                    | Nightly `pg_dump` rotation |
| `teller-enroll`  | `teller-sync/`     | `docker compose build teller-enroll`       | `docker compose run --rm teller-enroll`          | One-shot: upsert enrollment, fetch accounts, seed jobs |
| `teller-sync`    | `teller-sync/`     | `docker compose build teller-sync`         | `docker compose run --rm teller-sync`            | Pull balances/transactions for seeded accounts |

---

## Build, Run, and Sanity Checks

### 1) Database (`db`)

**Start & health**
```bash
docker compose up -d db
docker exec -it finance-db pg_isready -U $POSTGRES_USER -d $POSTGRES_DB
```

**Extensions**  
```bash
PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -p 5434 -U $POSTGRES_USER -d $POSTGRES_DB -c '\dx'
```
Expect: `pg_trgm`, `uuid-ossp`, `vector`.

---

### 2) Bootstrap (`db-bootstrap`)

**Run (idempotent)**  
```bash
docker compose up --no-deps db-bootstrap
docker compose up --no-deps db-bootstrap   # should say already applied
```

**Verify**  
```bash
PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -p 5434 -U $POSTGRES_USER -d $POSTGRES_DB   -c "select * from schema_migrations order by applied_at desc;"
```

---

### 3) Email Ingestor (`ingestor-email`)

**Build & run**
```bash
docker compose build ingestor-email
docker compose run --rm ingestor-email
```

**Verify**  
```bash
PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -p 5434 -U $POSTGRES_USER -d $POSTGRES_DB   -c "table ingest_files order by id desc limit 10;"
```
Expect rows with `status='received'` and file metadata.

---

### 4) Normalizer (`normalizer`)

**Build & run**
```bash
docker compose build normalizer
docker compose run --rm normalizer
```

**Verify**
```bash
# transactions landed
PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -p 5434 -U $POSTGRES_USER -d $POSTGRES_DB   -c "select id, posted_at, amount, description from transactions order by id desc limit 20;"

# files marked processed
PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -p 5434 -U $POSTGRES_USER -d $POSTGRES_DB   -c "table ingest_files order by id desc limit 10;"
```

---

### 5) Classifier (`classifier`)

**Config**: ensure `config/rules.yaml` exists at repo root and is mounted to `/app/config/rules.yaml`.

**Build & run**
```bash
docker compose build classifier
docker compose run --rm classifier
```

**Verify**
```bash
PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -p 5434 -U $POSTGRES_USER -d $POSTGRES_DB   -c "select t.id, t.posted_at, t.amount, t.description, c.code
      from tx_splits s
      join transactions t on t.id = s.transaction_id
      join categories c on c.id = s.category_id
      order by t.posted_at desc, t.id desc limit 20;"
```

---

### 6) Budget Importer (`budgeter`)

**Config**: `config/budgets.yaml` with category amounts; ensure categories are seeded (migration `0004_seed_categories.sql`).

**Build & run**
```bash
docker compose build budgeter
docker compose run --rm budgeter
```

**Verify**
```bash
# budgets written
PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -p 5434 -U $POSTGRES_USER -d $POSTGRES_DB   -c "select * from budgets order by category_id, period_start limit 20;"

# view shows budget vs actual
PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -p 5434 -U $POSTGRES_USER -d $POSTGRES_DB   -c "select * from v_budget_status order by category;"
```

---

### 7) Read-only API (`api`)

**Build & run**
```bash
docker compose build api
docker compose up -d api
```

**Health & endpoints**
```bash
curl -sS http://localhost:8010/healthz

# accounts
curl -sS http://localhost:8010/accounts | jq

# monthly spend (dates)
curl -sS 'http://localhost:8010/spend/monthly?frm=2025-09-01&to=2025-10-31' | jq

# monthly spend (YYYY-MM supported if you applied the coercion patch)
curl -sS 'http://localhost:8010/spend/monthly?frm=2025-09&to=2025-10' | jq

# budget status
curl -sS 'http://localhost:8010/budget/status?period=2025-10' | jq

# transactions
curl -sS 'http://localhost:8010/transactions?limit=20' | jq
curl -sS 'http://localhost:8010/transactions?uncategorized=true&limit=50' | jq
```

---

### 8) Scheduler (`scheduler`)

**Config**: In `.env`, set
```dotenv
HOST_WORKSPACE=/absolute/path/to/your/repo
DOCKER_SOCK_PATH=/run/user/1000/docker.sock
COMPOSE_PROJECT_NAME=finance   # match your running stack
```

**Build & run**
```bash
docker compose build scheduler
docker compose up -d scheduler
docker logs -f finance-scheduler
```

**Manual trigger (no waiting)**
```bash
docker exec -it finance-scheduler sh -lc   'docker compose -p "$COMPOSE_PROJECT_NAME" --project-directory "$HOST_WORKSPACE" -f "$HOST_WORKSPACE/docker-compose.yaml" run --rm --no-deps ingestor-email &&    docker compose -p "$COMPOSE_PROJECT_NAME" --project-directory "$HOST_WORKSPACE" -f "$HOST_WORKSPACE/docker-compose.yaml" run --rm --no-deps normalizer &&    docker compose -p "$COMPOSE_PROJECT_NAME" --project-directory "$HOST_WORKSPACE" -f "$HOST_WORKSPACE/docker-compose.yaml" run --rm --no-deps classifier'
```

**Verify**: recent `ingest_files` rows and increasing `transactions` count after ticks.

---

### 9) Backups (`backup`)

**Build & run**
```bash
docker compose build backup
docker compose up -d backup
```

**Verify** (after next run)
```bash
docker exec -it finance-backup sh -lc 'ls -lt /backups | head'
```

---

### 10) Teller Enroll (`teller-enroll`)

**Prereqs**
- Client certificate and key from Teller at `./secrets/teller/{certificate.pem,private_key.pem}` (mounted read-only).
- `.env` has `TELLER_AUTH_STYLE=basic`, valid `TELLER_ENROLLMENT_ID` (usr_*) and `TELLER_ACCESS_TOKEN` (token_*).

**One-time sanity with curl**
```bash
curl -v https://api.teller.io/accounts   --cert ./secrets/teller/certificate.pem   --key  ./secrets/teller/private_key.pem   -H 'Accept: application/json'   -H 'User-Agent: finance-os/0.1 (teller-enroll)'   -H "X-Enrollment-Id: $TELLER_ENROLLMENT_ID"   -u "$TELLER_ACCESS_TOKEN:"
```
Expect `HTTP/2 200` and a JSON array of accounts.

**Build & run**
```bash
docker compose build teller-enroll
docker compose run --rm teller-enroll
```

**Verify**
```sql
-- enrollment row
select id, provider, enrollment_id, environment, status
from provider_enrollments
order by id desc limit 1;

-- provider ↔ app accounts created
select count(*) from provider_accounts where enrollment_id = '<your usr_*>';
select count(*) from accounts where external_id like 'teller:%';

-- jobs seeded for each account
select provider_account_id, account_api_id, start_date, end_date, run_after
from teller_jobs
order by run_after desc limit 10;
```

---

### 11) Teller Sync (`teller-sync`)

**Build & run**
```bash
docker compose build teller-sync
docker compose run --rm teller-sync
```

**Verify**
```sql
select posted_at, amount, description
from transactions
order by posted_at desc, id desc
limit 20;
```

---

## Suggested Run Order

```bash
# First-time
docker compose up -d db
docker compose up --no-deps db-bootstrap

# Teller: enroll accounts, then sync
docker compose run --rm teller-enroll
docker compose run --rm teller-sync

# Email ingestion loop (manual)
docker compose run --rm ingestor-email
docker compose run --rm normalizer
docker compose run --rm classifier

# Budgets
docker compose run --rm budgeter

# API
docker compose up -d api

# Scheduler & backup
docker compose up -d scheduler backup
```

---

## Troubleshooting

- **API “port already allocated”**  
  Another process uses 8000. Change mapping to `127.0.0.1:8010:8000` (already set).

- **Classifier can’t find rules**  
  Ensure `config/rules.yaml` exists and is mounted to `/app/config/rules.yaml`.

- **Normalizer ON CONFLICT error**  
  Ensure migrations add:
  - `unique (name)` on `institutions`
  - `unique (institution_id, mask) where mask is not null` on `accounts`

- **Scheduler “permission denied /workspace”**  
  Use real host path: set `HOST_WORKSPACE`, and pass `--project-directory "$HOST_WORKSPACE" -f "$HOST_WORKSPACE/docker-compose.yaml"`.

- **Scheduler “cannot connect to Docker daemon”**  
  `DOCKER_SOCK_PATH` incorrect; set to your rootless socket and mount it.

- **psql “role root does not exist”**  
  You didn’t pass credentials. Use:  
  `PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -p 5434 -U $POSTGRES_USER -d $POSTGRES_DB -c 'select 1'`

### Troubleshooting (Teller)

- **Teller 401**  
  Check `.env`: `TELLER_AUTH_STYLE=basic`, non-empty `TELLER_ACCESS_TOKEN`, header `X-Enrollment-Id` present. Re-run `teller-enroll`.

- **Teller 403**  
  Token environment mismatch. Confirm `TELLER_BASE_URL` matches the environment the token was issued for.

- **TLS error**  
  Ensure `./secrets/teller/private_key.pem` matches `certificate.pem`:
  ```bash
  openssl x509 -noout -modulus -in ./secrets/teller/certificate.pem
  openssl rsa  -noout -modulus -in ./secrets/teller/private_key.pem
  ```
  Modulus values must match. Use an unencrypted key.

- **No jobs seeded**  
  Enrollment ran but no accounts returned. Verify curl to `/accounts` returns your accounts and your DB migrations include `teller_jobs` with the uniqueness guard.

---

## Cloud Notes

- **DB**: Managed Postgres (private IP). Run `db-bootstrap` as a scheduled job for grants + migrations.
- **Runtime**: Build images to a registry. Deploy `api` and any webhooks to your container platform. Use a scheduler to trigger jobs for ingestion, normalization, rules, and budgets.
- **Secrets**: Move env secrets to a secrets manager.
- **Backups**: Push dumps to object storage with lifecycle rules (e.g., 30–90 days).
