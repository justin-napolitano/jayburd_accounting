# enroll.py
import os, sys
from datetime import date, timedelta
import psycopg, requests

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

ENROLLMENT_ID = os.environ.get("TELLER_ENROLLMENT_ID")
ACCESS_TOKEN  = os.environ.get("TELLER_ACCESS_TOKEN")    # may be required by your setup
ENVIRONMENT   = os.getenv("TELLER_ENV", "sandbox")
USER_REF      = os.getenv("USER_REF", None)               # optional: “me”, email, etc.
SINCE_DAYS    = int(os.getenv("TELLER_SINCE_DAYS", "30"))

UA = "finance-os/0.1 (teller-enroll)"

# ---------- Helpers ----------
def http():
    if not ENROLLMENT_ID:
        raise SystemExit("TELLER_ENROLLMENT_ID is required")
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "application/json"})
    s.cert = (CERT_PATH, KEY_PATH)
    s.verify = CA_PATH if CA_PATH else True
    if ACCESS_TOKEN:
        s.headers["Authorization"] = f"Bearer {ACCESS_TOKEN}"
    return s

def jget(s, path, params=None):
    r = s.get(f"{BASE_URL}{path}", params=params, timeout=20)
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code} GET {path}: {r.text[:200]}")
    return r.json()

def pg():
    return psycopg.connect(DB_DSN)

def ensure_extensions(cur):
    # you likely already have these from init; harmless if already present
    cur.execute("create extension if not exists pgcrypto")

def upsert_enrollment(cur):
    # Store the access token encrypted with pgcrypto; require FIN_ENC_KEY
    enc_key = os.getenv("FIN_ENC_KEY")
    if not enc_key:
        raise SystemExit("FIN_ENC_KEY is required to encrypt the access token (pgcrypto).")

    cur.execute("""
      insert into provider_enrollments(provider, enrollment_id, user_ref, institution_name, environment, access_token_enc, status)
      values ('teller', %s, %s, %s, %s, pgp_sym_encrypt(coalesce(%s,''), %s), 'active')
      on conflict (enrollment_id) do update
        set environment = excluded.environment,
            access_token_enc = excluded.access_token_enc,
            status = 'active',
            user_ref = excluded.user_ref,
            institution_name = excluded.institution_name
      returning id
    """, (ENROLLMENT_ID, USER_REF, 'Teller', ENVIRONMENT, ACCESS_TOKEN or "", enc_key))
    return cur.fetchone()[0]

def map_type(t, st):
    t = (t or "").lower(); st = (st or "").lower()
    if t in ("depository","bank","cash"):
        if "checking" in st: return "checking"
        if "savings" in st:  return "savings"
        return "checking"
    if t in ("credit","card","credit_card"): return "credit"
    if t in ("loan","mortgage"): return "loan"
    if t in ("investment","brokerage"): return "investment"
    return None

def ensure_institution(cur):
    cur.execute("""
      insert into institutions(name, external_id)
      values ('TELLER','teller')
      on conflict (name) do nothing
      returning id
    """)
    row = cur.fetchone()
    if row: return row[0]
    cur.execute("select id from institutions where external_id='teller'")
    return cur.fetchone()[0]

def upsert_app_account(cur, inst_id, acct):
    # Upsert into your main "accounts" table used by API
    api_id = acct.get("id")
    name   = acct.get("name") or acct.get("official_name") or acct.get("account") or "Account"
    last4  = acct.get("last_four") or acct.get("last4") or acct.get("last4_digits")
    typ    = map_type(acct.get("type"), acct.get("subtype"))
    curr   = (acct.get("currency") or "USD").upper()[:3]
    cur.execute("""
      insert into accounts(institution_id, name, type, currency, mask, external_id, is_active)
      values (%s,%s,%s,%s,%s,%s,true)
      on conflict (external_id) do update set
        institution_id=excluded.institution_id,
        name=excluded.name,
        type=coalesce(excluded.type, accounts.type),
        currency=excluded.currency,
        mask=excluded.mask,
        is_active=true
      returning id
    """, (inst_id, name, typ, curr, last4, f"teller:{api_id}"))
    return cur.fetchone()[0]

def upsert_provider_account(cur, acct):
    # Persist mapping in provider_accounts (for jobs & auditing)
    teller_acct_id = acct.get("id")
    last4  = acct.get("last_four") or acct.get("last4") or acct.get("last4_digits")
    typ    = (acct.get("type") or "").lower()
    sub    = (acct.get("subtype") or "").lower()
    curr   = (acct.get("currency") or "USD").upper()[:3]

    cur.execute("""
      insert into provider_accounts(enrollment_id, teller_account_id, institution_id, last_four, type, subtype, currency)
      values (%s,%s,%s,%s,%s,%s,%s)
      on conflict (enrollment_id, teller_account_id) do update set
        institution_id = excluded.institution_id,
        last_four = excluded.last_four,
        type = excluded.type,
        subtype = excluded.subtype,
        currency = excluded.currency
      returning id
    """, (ENROLLMENT_ID, teller_acct_id, None, last4, typ, sub, curr))
    return cur.fetchone()[0]

def seed_initial_job(cur, provider_account_id, account_api_id, start_date, end_date):
    # Unique guard created in migration 0011__teller_jobs_unique.sql
    cur.execute("""
      insert into teller_jobs(provider_account_id, account_api_id, start_date, end_date, run_after)
      values (%s,%s,%s,%s, now())
      on conflict on constraint uq_teller_jobs_window_queued do nothing
    """, (provider_account_id, account_api_id, start_date, end_date))

def main():
    s = http()

    # If your tenant requires Authorization, enforce it
    if "Authorization" not in s.headers:
        print("[enroll] WARNING: no TELLER_ACCESS_TOKEN set; /accounts will likely return 401", file=sys.stderr)

    window_end   = date.today()
    window_start = window_end - timedelta(days=SINCE_DAYS)

    with pg() as conn, conn.cursor() as cur:
        ensure_extensions(cur)
        inst_id = ensure_institution(cur)

        # 1) Store/refresh enrollment (encrypted token in DB)
        enroll_id = upsert_enrollment(cur)

        # 2) Pull accounts for this enrollment
        accounts = jget(s, "/accounts")
        if isinstance(accounts, dict) and "data" in accounts:
            accounts = accounts["data"]

        # 3) Upsert into provider_accounts + app accounts, seed jobs
        count = 0
        for acct in accounts or []:
            api_id = acct.get("id")
            if not api_id:
                continue
            prov_id = upsert_provider_account(cur, acct)
            app_acct_id = upsert_app_account(cur, inst_id, acct)
            seed_initial_job(cur, prov_id, api_id, window_start, window_end)
            count += 1

        conn.commit()
        print(f"[enroll] enrollment={ENROLLMENT_ID} accounts={count} jobs_seeded<=accounts")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
