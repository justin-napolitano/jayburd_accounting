# enroll.py
# Pull Teller accounts for an enrollment and seed sync jobs.
# Defaults to Basic auth (token as username, empty password) with mTLS.
# Expects your DB schema to already exist (provider_enrollments, provider_accounts, institutions, accounts, teller_jobs).

import os
import sys
from datetime import date, timedelta

import psycopg
import requests
from requests.auth import HTTPBasicAuth

# ---------- Config ----------
DB_DSN = (
    f"host={os.environ['POSTGRES_HOST']} "
    f"port={os.environ['POSTGRES_PORT']} "
    f"dbname={os.environ['POSTGRES_DB']} "
    f"user={os.environ['POSTGRES_USER']} "
    f"password={os.environ['POSTGRES_PASSWORD']}"
)

BASE_URL   = os.getenv("TELLER_BASE_URL", "https://api.teller.io").rstrip("/")
CERT_PATH  = os.environ["TELLER_CERT"]
KEY_PATH   = os.environ["TELLER_KEY"]
CA_PATH    = os.getenv("TELLER_CA_PATH", "/etc/ssl/certs/ca-certificates.crt")

# Auth
ENROLLMENT_ID = os.environ.get("TELLER_ENROLLMENT_ID")     # this is the usr_* identifier you pass as X-Enrollment-Id
ACCESS_TOKEN  = os.environ.get("TELLER_ACCESS_TOKEN", "")  # for Basic: token as username, blank password
AUTH_STYLE    = os.getenv("TELLER_AUTH_STYLE", "basic").lower()  # "basic" (default) or "bearer"

# App behavior
ENVIRONMENT   = os.getenv("TELLER_ENV", "sandbox")
USER_REF      = os.getenv("USER_REF")  # optional: “me”, email, etc.
SINCE_DAYS    = int(os.getenv("TELLER_SINCE_DAYS", "30"))
FIN_ENC_KEY   = os.getenv("FIN_ENC_KEY")  # required to encrypt token

UA = "finance-os/0.1 (teller-enroll)"


# ---------- Helpers ----------
def http():
    if not ENROLLMENT_ID:
        raise SystemExit("TELLER_ENROLLMENT_ID is required")
    if not os.path.exists(CERT_PATH) or not os.path.exists(KEY_PATH):
        raise SystemExit(f"Client cert/key missing: {CERT_PATH} / {KEY_PATH}")
    if AUTH_STYLE not in ("basic", "bearer"):
        raise SystemExit(f"Unknown TELLER_AUTH_STYLE={AUTH_STYLE}")
    if not ACCESS_TOKEN:
        raise SystemExit("TELLER_ACCESS_TOKEN is required")

    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "application/json"})
    s.cert = (CERT_PATH, KEY_PATH)
    s.verify = CA_PATH if CA_PATH else True
    s.headers["X-Enrollment-Id"] = ENROLLMENT_ID

    if AUTH_STYLE == "basic":
        s.auth = HTTPBasicAuth(ACCESS_TOKEN, "")
    else:
        s.headers["Authorization"] = f"Bearer {ACCESS_TOKEN}"
    return s


def jget(s: requests.Session, path: str, params=None):
    url = f"{BASE_URL}{path}"
    r = s.get(url, params=params, timeout=20)
    if r.status_code >= 400:
        raise RuntimeError(
            f"HTTP {r.status_code} GET {url} resp={r.text[:500]} "
            f"auth_style={AUTH_STYLE} have_auth={'Authorization' in s.headers or s.auth is not None} "
            f"enrollment={s.headers.get('X-Enrollment-Id')}"
        )
    return r.json()


def pg():
    return psycopg.connect(DB_DSN)


def ensure_extensions(cur):
    cur.execute("create extension if not exists pgcrypto")


def has_column(cur, table_name: str, column_name: str) -> bool:
    cur.execute(
        """
        select 1
          from information_schema.columns
         where table_name = %s
           and column_name = %s
        """,
        (table_name, column_name),
    )
    return cur.fetchone() is not None


def upsert_enrollment(cur):
    """
    Store or refresh the enrollment row. Encrypt the access token with pgcrypto.
    Required table columns (your current schema):
      provider, enrollment_id, user_ref, institution_name, environment, access_token_enc, status
    Optional columns we set if present:
      teller_user_id, teller_enrollment_id
    """
    if not FIN_ENC_KEY:
        raise SystemExit("FIN_ENC_KEY is required to encrypt the access token (pgcrypto).")

    cur.execute(
        """
        insert into provider_enrollments
            (provider, enrollment_id, user_ref, institution_name, environment, access_token_enc, status)
        values ('teller', %s, %s, %s, %s, pgp_sym_encrypt(coalesce(%s,''), %s), 'active')
        on conflict (enrollment_id) do update
           set environment = excluded.environment,
               access_token_enc = excluded.access_token_enc,
               status = 'active',
               user_ref = excluded.user_ref,
               institution_name = excluded.institution_name
        returning id
        """,
        (ENROLLMENT_ID, USER_REF, 'Teller', ENVIRONMENT, ACCESS_TOKEN or "", FIN_ENC_KEY),
    )
    row_id = cur.fetchone()[0]

    # If optional columns exist, set a sane baseline
    if has_column(cur, "provider_enrollments", "teller_user_id"):
        cur.execute(
            "update provider_enrollments set teller_user_id = %s where id = %s and teller_user_id is distinct from %s",
            (ENROLLMENT_ID, row_id, ENROLLMENT_ID),
        )

    return row_id


def map_type(t, st):
    t = (t or "").lower()
    st = (st or "").lower()
    if t in ("depository", "bank", "cash"):
        if "checking" in st:
            return "checking"
        if "savings" in st:
            return "savings"
        return "checking"
    if t in ("credit", "card", "credit_card"):
        return "credit"
    if t in ("loan", "mortgage"):
        return "loan"
    if t in ("investment", "brokerage"):
        return "investment"
    return None


def ensure_institution(cur):
    cur.execute(
        """
        insert into institutions(name, external_id)
        values ('TELLER','teller')
        on conflict (name) do nothing
        returning id
        """
    )
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute("select id from institutions where external_id='teller'")
    return cur.fetchone()[0]


def upsert_app_account(cur, inst_id, acct):
    api_id = acct.get("id")
    name = acct.get("name") or acct.get("official_name") or acct.get("account") or "Account"
    last4 = acct.get("last_four") or acct.get("last4") or acct.get("last4_digits")
    typ = map_type(acct.get("type"), acct.get("subtype"))
    curr = (acct.get("currency") or "USD").upper()[:3]

    cur.execute(
        """
        insert into accounts(institution_id, name, type, currency, mask, external_id, is_active)
        values (%s,%s,%s,%s,%s,%s,true)
        on conflict (external_id) do update set
          institution_id = excluded.institution_id,
          name           = excluded.name,
          type           = coalesce(excluded.type, accounts.type),
          currency       = excluded.currency,
          mask           = excluded.mask,
          is_active      = true
        returning id
        """,
        (inst_id, name, typ, curr, last4, f"teller:{api_id}"),
    )
    return cur.fetchone()[0]


def upsert_provider_account(cur, acct):
    teller_acct_id = acct.get("id")
    last4 = acct.get("last_four") or acct.get("last4") or acct.get("last4_digits")
    typ = (acct.get("type") or "").lower()
    sub = (acct.get("subtype") or "").lower()
    curr = (acct.get("currency") or "USD").upper()[:3]

    cur.execute(
        """
        insert into provider_accounts
            (enrollment_id, teller_account_id, institution_id, last_four, type, subtype, currency)
        values (%s,%s,%s,%s,%s,%s,%s)
        on conflict (enrollment_id, teller_account_id) do update set
            institution_id = excluded.institution_id,
            last_four      = excluded.last_four,
            type           = excluded.type,
            subtype        = excluded.subtype,
            currency       = excluded.currency
        returning id
        """,
        (ENROLLMENT_ID, teller_acct_id, None, last4, typ, sub, curr),
    )
    return cur.fetchone()[0]


def seed_initial_job(cur, provider_account_id, account_api_id, start_date, end_date):
    # Idempotent insert guarded by a unique constraint on (provider_account_id, start_date, end_date)
    cur.execute(
        """
        insert into teller_jobs(provider_account_id, account_api_id, start_date, end_date, run_after)
        values (%s,%s,%s,%s, now())
        on conflict do nothing
        """,
        (provider_account_id, account_api_id, start_date, end_date),
    )


def main():
    s = http()
    window_end = date.today()
    window_start = window_end - timedelta(days=SINCE_DAYS)

    with pg() as conn, conn.cursor() as cur:
        ensure_extensions(cur)
        inst_id = ensure_institution(cur)

        # 1) Upsert enrollment and encrypted token
        enroll_row_id = upsert_enrollment(cur)

        # 2) Pull accounts via API
        accounts = jget(s, "/accounts")
        if isinstance(accounts, dict) and "data" in accounts:
            accounts = accounts["data"]

        # 3) Persist and seed jobs
        count = 0
        enr_seen = None
        for acct in accounts or []:
            api_id = acct.get("id")
            if not api_id:
                continue

            # capture the true Teller enrollment id if present (enr_*)
            enr = acct.get("enrollment_id")
            if enr and enr != enr_seen:
                enr_seen = enr
                if has_column(cur, "provider_enrollments", "teller_enrollment_id"):
                    cur.execute(
                        "update provider_enrollments set teller_enrollment_id = %s where id = %s",
                        (enr, enroll_row_id),
                    )

            prov_id = upsert_provider_account(cur, acct)
            _ = upsert_app_account(cur, inst_id, acct)
            seed_initial_job(cur, prov_id, api_id, window_start, window_end)
            count += 1

        conn.commit()
        print(f"[enroll] enrollment_header={ENROLLMENT_ID} accounts={count} jobs_seeded<=accounts")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
