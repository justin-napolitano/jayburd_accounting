# Finance OS (Headless) — Docker Build & Sanity Guide

This README documents how to build, run, and sanity-check each service in the headless finance stack. It assumes you’re running Docker Compose locally and using CSV/OFX email ingestion first, with a clean path to add Teller and other providers.

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
  - [Web UI (finance-web)](#12-web-ui-finance-web)
  - [Reverse Proxy (finance-proxy)](#13-reverse-proxy-finance-proxy)
- [Suggested Run Order](#suggested-run-order)
- [Troubleshooting](#troubleshooting)
  - [Teller](#troubleshooting-teller)
  - [Web & Proxy](#troubleshooting-web--proxy)
- [Cloud Notes](#cloud-notes)

---

## Prerequisites

- **Docker & Docker Compose** installed and running (rootless Docker is fine).
- A **`.env`** file at repo root (see below).
- **psql** client for DB checks (optional but useful).
- **curl** (and optionally **jq**) for API/UI checks.

> Host port mappings used here (defaults):
> - Postgres exposed at **localhost:5434** → container 5432  
> - API stays internal (no host port) once reverse proxy is used  
> - Proxy exposed at **<HOST_LAN_IP>:3020** → serves UI at `/` and API at `/api`

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
PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -p 5434 -U $POSTGRES_USER -d $POSTGRES_DB -c '\dx'
PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -p 5434 -U $POSTGRES_USER -d $POSTGRES_DB -c 'table schema_migrations;'
```

---

## Service Matrix

| Service            | Path                 | Build                                      | Run                                              | Purpose |
|--------------------|----------------------|--------------------------------------------|--------------------------------------------------|---------|
| `db`               | `db/`                | n/a (official image)                       | `docker compose up -d db`                        | Postgres with extensions |
| `db-bootstrap`     | `ops/scripts/`       | n/a (official image)                       | `docker compose up --no-deps db-bootstrap`       | Idempotent roles + migrations |
| `ingestor-email`   | `ingestor-email/`    | `docker compose build ingestor-email`      | `docker compose run --rm ingestor-email`         | Pull email attachments (CSV/OFX/QFX) |
| `normalizer`       | `normalizer/`        | `docker compose build normalizer`          | `docker compose run --rm normalizer`             | Normalize raw files to `transactions` |
| `classifier`       | `classifier/`        | `docker compose build classifier`          | `docker compose run --rm classifier`             | Apply keyword rules → `tx_splits` |
| `budgeter`         | `budgeter/`          | `docker compose build budgeter`            | `docker compose run --rm budgeter`               | Import monthly budgets from YAML |
| `api`              | `api/`               | `docker compose build api`                 | `docker compose up -d api`                       | Read-only HTTP API (internal only when proxied) |
| `scheduler`        | `scheduler/`         | `docker compose build scheduler`           | `docker compose up -d scheduler`                 | Cron-like orchestration of jobs |
| `backup`           | `backup/`            | `docker compose build backup`              | `docker compose up -d backup`                    | Nightly `pg_dump` rotation |
| `teller-enroll`    | `teller-sync/`       | `docker compose build teller-enroll`       | `docker compose run --rm teller-enroll`          | One-shot: upsert enrollment, fetch accounts, seed jobs |
| `teller-sync`      | `teller-sync/`       | `docker compose build teller-sync`         | `docker compose run --rm teller-sync`            | Pull balances/transactions for seeded accounts |
| `finance-web`      | `finance-web/`       | `docker compose build finance-web`         | internal only (served via proxy)                 | Next.js UI (built with API base `/api`) |
| `reverse-proxy`    | `ops/reverse-proxy/` | n/a (official image)                       | `docker compose up -d reverse-proxy`             | Serves UI at `/` and proxies API at `/api` |

---

## Build, Run, and Sanity Checks

### 1) Database (`db`)
```bash
docker compose up -d db
docker exec -it finance-db pg_isready -U $POSTGRES_USER -d $POSTGRES_DB
PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -p 5434 -U $POSTGRES_USER -d $POSTGRES_DB -c '\dx'
```

---

### 2) Bootstrap (`db-bootstrap`)
```bash
docker compose up --no-deps db-bootstrap
PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -p 5434 -U $POSTGRES_USER -d $POSTGRES_DB \
  -c "select * from schema_migrations order by applied_at desc;"
```

---

### 3) Email Ingestor (`ingestor-email`)
```bash
docker compose build ingestor-email
docker compose run --rm ingestor-email
PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -p 5434 -U $POSTGRES_USER -d $POSTGRES_DB \
  -c "table ingest_files order by id desc limit 10;"
```

---

### 4) Normalizer (`normalizer`)
```bash
docker compose build normalizer
docker compose run --rm normalizer
PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -p 5434 -U $POSTGRES_USER -d $POSTGRES_DB \
  -c "select id, posted_at, amount, description from transactions order by id desc limit 20;"
```

---

### 5) Classifier (`classifier`)
```bash
docker compose build classifier
docker compose run --rm classifier
PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -p 5434 -U $POSTGRES_USER -d $POSTGRES_DB \
  -c "select t.id, t.posted_at, t.amount, t.description, c.code
      from tx_splits s
      join transactions t on t.id = s.transaction_id
      join categories c on c.id = s.category_id
      order by t.posted_at desc, t.id desc limit 20;"
```

---

### 6) Budget Importer (`budgeter`)
```bash
docker compose build budgeter
docker compose run --rm budgeter
PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -p 5434 -U $POSTGRES_USER -d $POSTGRES_DB \
  -c "select * from budgets order by category_id, period_start limit 20;"
```

---

### 7) Read-only API (`api`)
Keep API internal when proxied (no host port). Health:
```bash
docker compose build api
docker compose up -d api
docker exec -it finance-api wget -qO- http://localhost:8000/healthz
```

---

### 8) Scheduler (`scheduler`)
```bash
docker compose build scheduler
docker compose up -d scheduler
docker logs -f finance-scheduler
```

Manual “ingest → normalize → classify”:
```bash
docker exec -it finance-scheduler sh -lc \
  'docker compose -p "$COMPOSE_PROJECT_NAME" --project-directory "$HOST_WORKSPACE" -f "$HOST_WORKSPACE/docker-compose.yaml" run --rm --no-deps ingestor-email && \
   docker compose -p "$COMPOSE_PROJECT_NAME" --project-directory "$HOST_WORKSPACE" -f "$HOST_WORKSPACE/docker-compose.yaml" run --rm --no-deps normalizer && \
   docker compose -p "$COMPOSE_PROJECT_NAME" --project-directory "$HOST_WORKSPACE" -f "$HOST_WORKSPACE/docker-compose.yaml" run --rm --no-deps classifier'
```

---

### 9) Backups (`backup`)
```bash
docker compose build backup
docker compose up -d backup
docker exec -it finance-backup sh -lc 'ls -lt /backups | head'
```

---

### 10) Teller Enroll (`teller-enroll`)

**Sanity**
```bash
curl -v https://api.teller.io/accounts \
  --cert ./secrets/teller/certificate.pem \
  --key  ./secrets/teller/private_key.pem \
  -H 'Accept: application/json' \
  -H 'User-Agent: finance-os/0.1 (teller-enroll)' \
  -H "X-Enrollment-Id: $TELLER_ENROLLMENT_ID" \
  -u "$TELLER_ACCESS_TOKEN:"
```

**Run**
```bash
docker compose build teller-enroll
docker compose run --rm teller-enroll
```

**Verify DB**
```sql
select count(*) from accounts where external_id like 'teller:%';
select count(*) from teller_jobs;
```

---

### 11) Teller Sync (`teller-sync`)
```bash
docker compose build teller-sync
docker compose run --rm teller-sync
PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -p 5434 -U $POSTGRES_USER -d $POSTGRES_DB \
  -c "select posted_at, amount, description from transactions order by posted_at desc, id desc limit 20;"
```

---

### 12) Web UI (`finance-web`)

Build the UI with API base **`/api`** so the browser calls the proxy, not the API directly:
```bash
# one-time: ensure .dockerignore keeps .next, node_modules, .git out of context
docker compose build finance-web
```

Do not publish a host port for `finance-web`. It will be served through the proxy.

---

### 13) Reverse Proxy (`finance-proxy`)

The proxy exposes **3020** on the host, serves the UI at `/`, and forwards API calls at `/api` to the internal `api` service.

Bring it up:
```bash
docker compose up -d reverse-proxy
```

Sanity from any device on your LAN (replace with your host IP if different):
```bash
curl -i http://192.168.1.115:3020/healthz          # expect 200 ok
curl -I http://192.168.1.115:3020/                  # UI HTML headers
curl -i http://192.168.1.115:3020/api/accounts      # API JSON, no CORS
```

Open the app:  
`http://192.168.1.115:3020/`

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

# API (internal only) + UI + Proxy
docker compose up -d api finance-web reverse-proxy

# Scheduler & backup
docker compose up -d scheduler backup
```

---

## Troubleshooting

- **API “port already allocated”**  
  If you previously published 8010 and now use the proxy, remove the API host port mapping. Keep API internal.

- **Classifier can’t find rules**  
  Ensure `config/rules.yaml` exists and is mounted to `/app/config/rules.yaml`.

- **Normalizer ON CONFLICT error**  
  Ensure migrations add:
  - `unique (name)` on `institutions`
  - `unique (institution_id, mask) where mask is not null` on `accounts`

- **Scheduler “permission denied /workspace”**  
  Set a real absolute `HOST_WORKSPACE` path and pass `--project-directory "$HOST_WORKSPACE"`.

- **Scheduler “cannot connect to Docker daemon”**  
  Mount the correct rootless Docker socket: `DOCKER_SOCK_PATH=/run/user/<uid>/docker.sock`.

- **psql “role root does not exist”**  
  Use credentials explicitly:
  ```bash
  PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -p 5434 -U $POSTGRES_USER -d $POSTGRES_DB -c 'select 1'
  ```

### Troubleshooting (Teller)

- **401 Unauthorized**  
  `.env` must have `TELLER_AUTH_STYLE=basic`, `TELLER_ACCESS_TOKEN` set, and you must send `X-Enrollment-Id`. Re-run `teller-enroll`.

- **403 Forbidden**  
  Environment mismatch. Ensure `TELLER_BASE_URL` matches the token’s environment.

- **TLS errors**  
  Key/cert mismatch or encrypted key. Verify modulus:
  ```bash
  openssl x509 -noout -modulus -in ./secrets/teller/certificate.pem
  openssl rsa  -noout -modulus -in ./secrets/teller/private_key.pem
  ```
  Values must match.

- **No jobs seeded**  
  Confirm `/accounts` returns data and the `teller_jobs` uniqueness constraint exists.

### Troubleshooting (Web & Proxy)

- **CORS errors in browser**  
  You bypass CORS by using the proxy. Ensure the UI was built with `NEXT_PUBLIC_API_BASE=/api`. Rebuild `finance-web` if you changed it.

- **Proxy 502/404**  
  Proxy can’t reach backends. Check service names/ports in the proxy config. From proxy container:
  ```bash
  docker exec -it finance-proxy sh -lc 'wget -qO- http://finance-web:3020/healthz && echo && wget -qO- http://finance-api:8000/healthz'
  ```

- **LAN access blocked**  
  If Ubuntu `ufw` is enabled:
  ```bash
  sudo ufw allow from 192.168.1.0/24 to any port 3020 proto tcp
  ```

- **Frontend build failures**  
  Components using `usePathname`, `useRouter`, `useSearchParams` must be Client Components. Add `'use client';` at the top of those files.

---

## Cloud Notes

- **DB**: Managed Postgres (private IP). Run `db-bootstrap` as a job for grants + migrations.
- **Runtime**: Build images to a registry. Deploy `api`, `web`, and `proxy`. Use a scheduler for ingestion, normalization, rules, and budgets.
- **Secrets**: Move env secrets to a secrets manager and mount/inject at runtime.
- **Backups**: Dump to object storage with lifecycle policies (30–90 days).
