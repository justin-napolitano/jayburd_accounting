import os, csv, hashlib, json, glob
from datetime import datetime
from dateutil import parser as dparse
import chardet
import psycopg
import pandas as pd
from ofxparse import OfxParser

PG_DSN = f"host={os.environ['POSTGRES_HOST']} port={os.environ['POSTGRES_PORT']} dbname={os.environ['POSTGRES_DB']} user={os.environ['POSTGRES_USER']} password={os.environ['POSTGRES_PASSWORD']}"
RAW_DIR = os.getenv("RAW_DIR", "/data/raw")

def sha256_text(s: str) -> bytes:
    return hashlib.sha256(s.encode('utf-8')).digest()

def detect_encoding(path):
    with open(path, 'rb') as f:
        return chardet.detect(f.read(4096))['encoding'] or 'utf-8'

def load_file_bytes(path):
    with open(path, 'rb') as f:
        return f.read()

def stage_payload(conn, ingest_file_id, source, payload):
    with conn.cursor() as cur:
        cur.execute(
            "insert into tx_staging_raw(ingest_file_id, source, payload) values (%s,%s,%s)",
            (ingest_file_id, source, psycopg.types.json.Json(payload))
        )

def mark_processed(conn, ingest_file_id):
    with conn.cursor() as cur:
        cur.execute("update ingest_files set status='processed', processed_at=now() where id=%s", (ingest_file_id,))

def upsert_transaction(cur, acct_id, posted_at, amount, currency, desc, ext_id, balance_after):
    norm = ' '.join(desc.upper().split())
    h = sha256_text(f"{acct_id}|{posted_at.isoformat()}|{amount:.2f}|{norm}")
    cur.execute("""
        insert into transactions(account_id, posted_at, amount, currency, description, normalized_desc, external_tx_id, hash, balance_after)
        values (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        on conflict (account_id, external_tx_id) where external_tx_id is not null do update
          set updated_at = now()
        returning id
    """, (acct_id, posted_at, amount, currency, desc, norm, ext_id, psycopg.Binary(h), balance_after))
    if cur.rowcount == 0:
        # fallback to hash-based dedupe if no external id
        cur.execute("""
            insert into transactions(account_id, posted_at, amount, currency, description, normalized_desc, external_tx_id, hash, balance_after)
            values (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            on conflict (account_id, hash) do update
              set updated_at = now()
            returning id
        """, (acct_id, posted_at, amount, currency, desc, norm, ext_id, psycopg.Binary(h), balance_after))
    return cur.fetchone()[0]

def resolve_account(cur, bank:str, mask:str, currency:str):
    # naive: match by mask; in practice you’ll seed accounts table once.
    cur.execute("select id from accounts where mask=%s limit 1", (mask,))
    row = cur.fetchone()
    if row: return row[0]
    # create placeholder account if not exists
    cur.execute("""
      insert into institutions(name) values(%s)
      on conflict (name) do nothing
    """, (bank,))
    cur.execute("select id from institutions where name=%s", (bank,))
    inst_id = cur.fetchone()[0]
    cur.execute("""
      insert into accounts(institution_id, name, type, currency, mask, is_active)
      values (%s, %s, 'checking', %s, %s, true)
      returning id
    """, (inst_id, f"{bank}-{mask or 'XXXX'}", currency, mask))
    return cur.fetchone()[0]

def parse_csv_bytes(b:bytes):
    # return list of dict rows with minimal normalized keys
    text = b.decode(detect_encoding_bytes(b))
    sniffer = csv.Sniffer()
    dialect = sniffer.sniff(text.splitlines()[0] + '\n')
    reader = csv.DictReader(text.splitlines(), dialect=dialect)
    rows = []
    for r in reader:
        rows.append({k.strip().lower(): (v or '').strip() for k,v in r.items()})
    return rows

def detect_encoding_bytes(b):
    return chardet.detect(b)['encoding'] or 'utf-8'

def parse_ofx_bytes(b:bytes):
    ofx = OfxParser.parse_bytes(b)
    rows = []
    for acct in ofx.accounts:
        for tx in acct.statement.transactions:
            rows.append({
                "date": tx.date.strftime("%Y-%m-%d"),
                "amount": f"{tx.amount:.2f}",
                "fitid": tx.id or "",
                "name": tx.payee or tx.memo or "",
                "balance": ""
            })
    return rows

def normalize_row(row, bank):
    # Try common column names; adjust as you learn each bank
    date_val = row.get("date") or row.get("posted date") or row.get("posting date") or row.get("transaction date")
    desc = row.get("description") or row.get("name") or row.get("memo") or ""
    amt = row.get("amount") or row.get("amount(-)") or row.get("debit") or row.get("credit")
    fitid = row.get("fitid") or row.get("id") or ""
    bal = row.get("balance") or ""
    mask = row.get("account") or row.get("account number") or row.get("last4") or ""

    posted_at = dparse.parse(date_val).date()
    amount = float(str(amt).replace(",", ""))

    currency = (row.get("currency") or "USD").upper()
    return {
        "bank": bank, "mask": mask, "posted_at": posted_at,
        "amount": amount, "currency": currency,
        "description": desc.strip() or "UNKNOWN",
        "external_tx_id": fitid or None,
        "balance_after": float(bal.replace(",","")) if str(bal).strip() else None
    }

def process_file(conn, ingest_file):
    fid, source, bank, path = ingest_file
    with open(path, 'rb') as f:
        data = f.read()

    rows = []
    if path.lower().endswith((".ofx",".qfx")):
        rows = parse_ofx_bytes(data)
        stage_payload(conn, fid, 'ofx', rows)
    elif path.lower().endswith(".csv"):
        enc = detect_encoding(path)
        with open(path, 'r', encoding=enc, errors='ignore') as f:
            df = pd.read_csv(f)
        rows = df.to_dict(orient="records")
        stage_payload(conn, fid, 'csv', rows)
    else:
        # unsupported
        with conn.cursor() as cur:
            cur.execute("update ingest_files set status='error', error='unsupported file type' where id=%s", (fid,))
        return

    with conn.cursor() as cur:
        for r in rows:
            norm = normalize_row({k.lower(): ("" if v is None else str(v)) for k,v in r.items()}, bank or "unknown")
            acct_id = resolve_account(cur, norm["bank"], norm["mask"], norm["currency"])
            upsert_transaction(cur, acct_id, norm["posted_at"], norm["amount"], norm["currency"], norm["description"], norm["external_tx_id"], norm["balance_after"])
    mark_processed(conn, fid)
    print(f"[normalize] processed {path}")

def main():
    with psycopg.connect(PG_DSN, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("select id, source, bank, filename from ingest_files where status='received' order by id asc")
            files = cur.fetchall()
        if not files:
            print("[normalize] nothing to do"); return
        for ingest_file in files:
            process_file(conn, ingest_file)

if __name__ == "__main__":
    main()

