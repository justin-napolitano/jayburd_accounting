import os, hmac, hashlib, json
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import psycopg

DB_DSN = (
    f"host={os.environ['POSTGRES_HOST']} "
    f"port={os.environ['POSTGRES_PORT']} "
    f"dbname={os.environ['POSTGRES_DB']} "
    f"user={os.environ['POSTGRES_USER']} "
    f"password={os.environ['POSTGRES_PASSWORD']}"
)
WEBHOOK_SECRET = os.environ["TELLER_WEBHOOK_SECRET"].encode("utf-8")

app = FastAPI(title="Teller Webhook", version="0.1.0")

def verify_sig(body: bytes, sig_header: str | None):
    if not sig_header:
        return False
    # Minimal HMAC check. Teller sends an HMAC-SHA256 of the raw body with your secret.
    try:
        provided = bytes.fromhex(sig_header.strip())
    except Exception:
        return False
    digest = hmac.new(WEBHOOK_SECRET, body, hashlib.sha256).digest()
    return hmac.compare_digest(provided, digest)

@app.post("/teller/webhook")
async def webhook(request: Request):
    raw = await request.body()
    sig = request.headers.get("Teller-Signature") or request.headers.get("X-Teller-Signature")
    if not verify_sig(raw, sig):
        raise HTTPException(status_code=401, detail="bad signature")

    try:
        evt = json.loads(raw.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="bad json")

    # Expect something like: { "type": "transactions.updated", "account_id": "acc_..." }
    account_api_id = (evt.get("account_id") or evt.get("data", {}).get("account_id"))
    if not account_api_id:
        # be permissive; no account id means nothing to do
        return JSONResponse({"status": "ignored"}, status_code=200)

    reason = evt.get("type") or "unknown"
    with psycopg.connect(DB_DSN) as conn, conn.cursor() as cur:
        cur.execute("""
          insert into teller_jobs(account_api_id, enqueue_reason)
          values (%s, %s)
          on conflict (account_api_id) do nothing
        """, (account_api_id, reason))
        conn.commit()

    return {"status": "enqueued", "account_api_id": account_api_id}
