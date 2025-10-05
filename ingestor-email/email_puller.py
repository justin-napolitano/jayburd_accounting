import os, ssl, email, hashlib, mimetypes, time
from datetime import datetime
from imaplib import IMAP4_SSL
import psycopg
from email.parser import BytesParser

IMAP_HOST = os.environ["IMAP_HOST"]
IMAP_USER = os.environ["IMAP_USER"]
IMAP_PASS = os.environ["IMAP_PASS"]
IMAP_FOLDER = os.getenv("IMAP_FOLDER", "INBOX")
RAW_DIR = os.getenv("RAW_DIR", "/data/raw")
BANK_NAME = os.getenv("BANK_NAME", None)  # optional default bank label

PG_DSN = f"host={os.environ['POSTGRES_HOST']} port={os.environ['POSTGRES_PORT']} dbname={os.environ['POSTGRES_DB']} user={os.environ['POSTGRES_USER']} password={os.environ['POSTGRES_PASSWORD']}"

os.makedirs(RAW_DIR, exist_ok=True)
ctx = ssl.create_default_context()

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def save_attachment(bank_guess, filename, content):
    h = sha256_bytes(content)
    now = datetime.now()
    subdir = os.path.join(RAW_DIR, bank_guess or "unknown", now.strftime("%Y"), now.strftime("%m"))
    os.makedirs(subdir, exist_ok=True)
    safe = f"{h[:16]}_{filename}"
    path = os.path.join(subdir, safe)
    if not os.path.exists(path):
        with open(path, "wb") as f:
            f.write(content)
    return path, h, len(content), mimetypes.guess_type(filename)[0] or "application/octet-stream"

def upsert_ingest_file(cur, source, bank, path, h, size, mime):
    cur.execute(
        """
        insert into ingest_files(source, bank, filename, content_sha256, size_bytes, mime_type, status)
        values (%s,%s,%s,%s,%s,%s,'received')
        on conflict (content_sha256) do nothing
        """,
        (source, bank, path, h, size, mime)
    )

def main():
    with IMAP4_SSL(IMAP_HOST, ssl_context=ctx) as M:
        M.login(IMAP_USER, IMAP_PASS)
        M.select(IMAP_FOLDER)
        typ, data = M.search(None, 'UNSEEN')
        ids = data[0].split()
        if not ids:
            print("[email] nothing new")
            return
        with psycopg.connect(PG_DSN, autocommit=True) as conn:
            with conn.cursor() as cur:
                for num in ids:
                    typ, msgdata = M.fetch(num, '(RFC822)')
                    if typ != 'OK': continue
                    msg = BytesParser().parsebytes(msgdata[0][1])
                    bank_guess = BANK_NAME
                    subj = msg.get('Subject', '')
                    frm = msg.get('From','')
                    if bank_guess is None:
                        # naive guess: domain of From header
                        bank_guess = (frm.split('@')[-1].split('>')[0].split()[-1] if '@' in frm else 'unknown').split('.')[-2]

                    for part in msg.walk():
                        if part.get_content_disposition() == 'attachment':
                            fname = part.get_filename() or 'attachment.bin'
                            payload = part.get_payload(decode=True) or b''
                            if not payload:
                                continue
                            path, h, size, mime = save_attachment(bank_guess, fname, payload)
                            upsert_ingest_file(cur, 'email', bank_guess, path, h, size, mime)
                    # mark seen
                    M.store(num, '+FLAGS', '\\Seen')
        print(f"[email] processed {len(ids)} messages")

if __name__ == "__main__":
    main()

