import os, sys
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
import psycopg, requests

DB_DSN = (
    f"host={os.environ['POSTGRES_HOST']} "
    f"port={os.environ['POSTGRES_PORT']} "
    f"dbname={os.environ['POSTGRES_DB']} "
    f"user={os.environ['POSTGRES_USER']} "
    f"password={os.environ['POSTGRES_PASSWORD']}"
)

BASE_URL = os.getenv("TELLER_BASE_URL", "https://api.teller.io").rstrip("/")
CERT_PATH = os.environ["TELLER_CERT"]
KEY_PATH = os.environ["TELLER_KEY"]
CA_PATH = os.getenv("TELLER_CA_PATH", "/etc/ssl/certs/ca-certificates.crt")
SINCE_DAYS = int(os.getenv("TELLER_SINCE_DAYS", "30"))
UA = "finance-os/0.1 (teller-sync)"

def pg():
    return psycopg.connect(DB_DSN)

def http():
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "application/json"})
    s.cert = (CERT_PATH, KEY_PATH)
    s.verify = CA_PATH if CA_PATH else True
    return s

def jget(s, path, params=None):
    r = s.get(f"{BASE_URL}{path}", params=params, timeout=20)
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code} GET {path}: {r.text[:200]}")
    return r.json()

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

def upsert_account(cur, inst_id, acct):
    api_id = acct.get("id")
    name = acct.get("name") or acct.get("official_name") or acct.get("account") or "Account"
    last4 = acct.get("last_four") or acct.get("last4") or acct.get("last4_digits")
    typ = map_type(acct.get("type"), acct.get("subtype"))
    curr = (acct.get("currency") or "USD").upper()[:3]
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

def parse_amount(v):
    if isinstance(v,(int,float)): return Decimal(str(v)).quantize(Decimal("0.01"))
    if isinstance(v,str):
        try: return Decimal(v).quantize(Decimal("0.01"))
        except InvalidOperation:
            if v.isdigit(): return (Decimal(v)/Decimal(100)).quantize(Decimal("0.01"))
    raise ValueError(f"bad amount {v!r}")

def ndesc(s): return " ".join((s or "").strip().split()).upper()

def upsert_tx(cur, account_id, tx):
    ext = tx.get("id")
    d = tx.get("date") or tx.get("posted") or tx.get("timestamp") or tx.get("booked")
    if not d: raise ValueError(f"missing date in tx {ext}")
    posted = date.fromisoformat(str(d)[:10])
    desc = tx.get("description") or (tx.get("counterparty") or {}).get("name") or tx.get("name") or "Transaction"
    amt  = parse_amount(tx.get("amount"))
    curr = (tx.get("currency") or "USD").upper()[:3]
    cur.execute("""
      insert into transactions(account_id, posted_at, amount, currency, description, normalized_desc, external_tx_id)
      values (%s,%s,%s,%s,%s,%s,%s)
      on conflict (account_id, external_tx_id) do nothing
      returning id
    """, (account_id, posted, amt, curr, desc, ndesc(desc), ext))
    return cur.fetchone() is not None

def drain_jobs(s, cur, inst_id, window_start, window_end):
    cur.execute("""
      select id, account_api_id from teller_jobs
      where run_after <= now()
      order by id
      limit 50
    """)
    jobs = cur.fetchall()
    inserted_total = 0
    for job_id, api_id in jobs:
        try:
            acct = jget(s, f"/accounts/{api_id}")
            db_acct_id = upsert_account(cur, inst_id, acct)
            txs = jget(s, f"/accounts/{api_id}/transactions", params={"from": window_start.isoformat()})
            inserted = sum(1 for tx in txs if upsert_tx(cur, db_acct_id, tx))
            inserted_total += inserted
            cur.execute("delete from teller_jobs where id=%s", (job_id,))
            cur.execute("""
              insert into teller_sync(account_id, last_polled_at, last_window_start, last_window_end)
              values (%s, now(), %s, %s)
              on conflict (account_id) do update set last_polled_at=excluded.last_polled_at,
                                                    last_window_start=excluded.last_window_start,
                                                    last_window_end=excluded.last_window_end
            """, (db_acct_id, window_start, window_end))
            print(f"[sync] drained job {job_id} for {api_id}: +{inserted}")
        except Exception as e:
            cur.execute("update teller_jobs set attempts=attempts+1, last_error=%s, run_after=now()+interval '5 minutes' where id=%s", (str(e)[:500], job_id))
            print(f"[sync] job {job_id} failed: {e}", file=sys.stderr)
    return inserted_total, len(jobs)

def sweep_all_accounts(s, cur, inst_id, window_start, window_end):
    accounts = jget(s, "/accounts")
    if isinstance(accounts, dict) and "data" in accounts: accounts = accounts["data"]
    touched = 0; inserted_total = 0
    for acct in accounts:
        api_id = acct.get("id");  # teller account id
        if not api_id: continue
        db_acct_id = upsert_account(cur, inst_id, acct)
        touched += 1
        try:
            txs = jget(s, f"/accounts/{api_id}/transactions", params={"from": window_start.isoformat()})
        except Exception as e:
            print(f"[sync] warn fetch {api_id}: {e}", file=sys.stderr)
            continue
        inserted = sum(1 for tx in txs if upsert_tx(cur, db_acct_id, tx))
        inserted_total += inserted
        cur.execute("""
          insert into teller_sync(account_id, last_polled_at, last_window_start, last_window_end)
          values (%s, now(), %s, %s)
          on conflict (account_id) do update set last_polled_at=excluded.last_polled_at,
                                                last_window_start=excluded.last_window_start,
                                                last_window_end=excluded.last_window_end
        """, (db_acct_id, window_start, window_end))
        print(f"[sync] sweep {api_id}: +{inserted}")
    return touched, inserted_total

def main():
    s = http()
    window_end = date.today()
    window_start = window_end - timedelta(days=SINCE_DAYS)
    with pg() as conn, conn.cursor() as cur:
        inst_id = ensure_institution(cur)
        # drain jobs first
        inserted, job_count = drain_jobs(s, cur, inst_id, window_start, window_end)
        # if no jobs, do a sweep
        if job_count == 0:
            touched, ins = sweep_all_accounts(s, cur, inst_id, window_start, window_end)
            print(f"[sync] sweep done: accounts={touched}, new={ins}")
        else:
            print(f"[sync] drained jobs: new={inserted}, jobs={job_count}")
        conn.commit()

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: pass
