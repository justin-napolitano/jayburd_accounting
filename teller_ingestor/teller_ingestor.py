import os, sys, time, json
from datetime import date, timedelta, datetime
from decimal import Decimal, InvalidOperation
import requests
import psycopg

DB_DSN = (
    f"host={os.environ['POSTGRES_HOST']} "
    f"port={os.environ['POSTGRES_PORT']} "
    f"dbname={os.environ['POSTGRES_DB']} "
    f"user={os.environ.get('POSTGRES_USER')} "
    f"password={os.environ.get('POSTGRES_PASSWORD')}"
)

BASE_URL = os.getenv("TELLER_BASE_URL", "https://api.teller.io").rstrip("/")
CERT_PATH = os.environ["TELLER_CERT"]
KEY_PATH = os.environ["TELLER_KEY"]
CA_PATH = os.getenv("TELLER_CA_PATH", "/etc/ssl/certs/ca-certificates.crt")
SINCE_DAYS = int(os.getenv("TELLER_SINCE_DAYS", "30"))

UA = "finance-os/0.1 (teller-ingestor)"

def pg():
    return psycopg.connect(DB_DSN)

def http():
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "application/json"})
    s.cert = (CERT_PATH, KEY_PATH)
    s.verify = CA_PATH if CA_PATH else True
    s.timeout = 20
    return s

def get_json(s: requests.Session, path: str, params=None):
    url = f"{BASE_URL}{path}"
    r = s.get(url, params=params, timeout=20)
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code} GET {path}: {r.text[:200]}")
    try:
        return r.json()
    except Exception as e:
        raise RuntimeError(f"Bad JSON from {path}: {e}; body[:200]={r.text[:200]}")

def ensure_institution(cur) -> int:
    cur.execute("""
        insert into institutions(name, external_id)
        values ('TELLER', 'teller')
        on conflict (name) do nothing
        returning id
    """)
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute("select id from institutions where external_id = 'teller'")
    return cur.fetchone()[0]

def map_type(teller_type: str, subtype: str | None) -> str | None:
    t = (teller_type or "").lower()
    st = (subtype or "").lower() if subtype else ""
    # shove into our enum: checking|savings|credit|loan|investment|cash
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

def upsert_account(cur, inst_id: int, acct: dict) -> int:
    # Teller typical fields
    acc_id = acct.get("id")
    name = acct.get("name") or acct.get("official_name") or acct.get("account") or "Account"
    last4 = acct.get("last_four") or acct.get("last4") or acct.get("last4_digits")
    a_type = map_type(acct.get("type"), acct.get("subtype"))
    currency = (acct.get("currency") or "USD").upper()[:3]

    cur.execute("""
      insert into accounts(institution_id, name, type, currency, mask, external_id, is_active)
      values (%s, %s, %s, %s, %s, %s, true)
      on conflict (external_id) do update
        set institution_id = excluded.institution_id,
            name = excluded.name,
            type = coalesce(excluded.type, accounts.type),
            currency = excluded.currency,
            mask = excluded.mask,
            is_active = true
      returning id
    """, (inst_id, name, a_type, currency, last4, f"teller:{acc_id}"))
    return cur.fetchone()[0]

def parse_amount(v) -> Decimal:
    if isinstance(v, (int, float)):
        return Decimal(str(v)).quantize(Decimal("0.01"))
    if isinstance(v, str):
        try:
            return Decimal(v).quantize(Decimal("0.01"))
        except InvalidOperation:
            # Some APIs use cents integers as strings
            if v.isdigit():
                return (Decimal(v) / Decimal(100)).quantize(Decimal("0.01"))
    raise ValueError(f"bad amount: {v!r}")

def normalize_desc(s: str | None) -> str:
    if not s:
        return ""
    return " ".join(s.strip().split()).upper()

def upsert_tx(cur, account_id: int, tx: dict) -> bool:
    # Common Teller fields
    ext_id = tx.get("id")
    # date field names vary; try a few
    d = tx.get("date") or tx.get("posted") or tx.get("timestamp") or tx.get("booked")
    if not d:
        raise ValueError(f"missing date in tx {ext_id}")
    posted = date.fromisoformat(str(d)[:10])

    desc = tx.get("description") \
        or (tx.get("details") or {}).get("processing_status") \
        or (tx.get("counterparty") or {}).get("name") \
        or tx.get("name") \
        or "Transaction"
    amount = parse_amount(tx.get("amount"))
    curr = (tx.get("currency") or "USD").upper()[:3]

    cur.execute("""
      insert into transactions (account_id, posted_at, amount, currency, description, normalized_desc, external_tx_id)
      values (%s, %s, %s, %s, %s, %s, %s)
      on conflict (account_id, external_tx_id) do nothing
      returning id
    """, (account_id, posted, amount, curr, desc, normalize_desc(desc), ext_id))
    return cur.fetchone() is not None

def fetch_transactions(s: requests.Session, account_api_id: str, window_start: date):
    # Prefer query param "from" YYYY-MM-DD; if API complains, adjust to your version.
    params = {"from": window_start.isoformat()}
    path = f"/accounts/{account_api_id}/transactions"
    data = get_json(s, path, params=params)
    if isinstance(data, dict) and "data" in data:
        data = data["data"]
    if not isinstance(data, list):
        raise RuntimeError(f"unexpected tx payload for {account_api_id}: {type(data)}")
    return data

def main():
    s = http()
    window_end = date.today()
    window_start = window_end - timedelta(days=SINCE_DAYS)

    with pg() as conn, conn.cursor() as cur:
        inst_id = ensure_institution(cur)
        conn.commit()

    accounts = get_json(s, "/accounts")
    if isinstance(accounts, dict) and "data" in accounts:
        accounts = accounts["data"]

    created = 0
    touched_accounts = 0

    with pg() as conn, conn.cursor() as cur:
        inst_id = ensure_institution(cur)

        for acct in accounts:
            api_id = acct.get("id")
            if not api_id:
                continue

            db_acct_id = upsert_account(cur, inst_id, acct)
            touched_accounts += 1

            # Pull a rolling window; dedupe on insert with unique index
            try:
                txs = fetch_transactions(s, api_id, window_start)
            except Exception as e:
                print(f"[teller] warn: account {api_id} fetch failed: {e}", file=sys.stderr)
                continue

            inserted = 0
            for tx in txs:
                try:
                    if upsert_tx(cur, db_acct_id, tx):
                        inserted += 1
                        created += 1
                except Exception as e:
                    # keep going; one bad tx shouldn't nuke the batch
                    print(f"[teller] skip tx error: {e}", file=sys.stderr)
                    continue

            # sync metadata
            cur.execute("""
              insert into teller_sync(account_id, last_polled_at, last_window_start, last_window_end)
              values (%s, now(), %s, %s)
              on conflict (account_id) do update
                set last_polled_at = excluded.last_polled_at,
                    last_window_start = excluded.last_window_start,
                    last_window_end = excluded.last_window_end
            """, (db_acct_id, window_start, window_end))
            print(f"[teller] account {api_id}: +{inserted} new")

        conn.commit()

    print(f"[teller] done: accounts touched={touched_accounts}, transactions inserted={created}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
