import os, yaml, re
from datetime import date, timedelta
import psycopg

PG_DSN = (
    f"host={os.environ['POSTGRES_HOST']} "
    f"port={os.environ['POSTGRES_PORT']} "
    f"dbname={os.environ['POSTGRES_DB']} "
    f"user={os.environ['POSTGRES_USER']} "
    f"password={os.environ['POSTGRES_PASSWORD']}"
)

RULES_PATH = os.getenv("RULES_PATH", "/app/config/rules.yaml")
DAYS = int(os.getenv("CLASSIFY_LOOKBACK_DAYS", "120"))

def load_rules():
    with open(RULES_PATH, "r") as f:
        items = yaml.safe_load(f) or []
    # normalize
    rules = []
    for r in items:
        rules.append({
            "name": r["name"],
            "priority": int(r.get("priority", 100)),
            "includes": [s.upper() for s in r.get("includes", [])],
            "excludes": [s.upper() for s in r.get("excludes", [])],
            "category_code": r["category_code"],
            "amount_min": float(r.get("amount_min", -1e15)),
            "amount_max": float(r.get("amount_max",  1e15)),
        })
    return sorted(rules, key=lambda x: x["priority"])

def fetch_categories(cur):
    cur.execute("select id, code from categories")
    return {code: _id for _id, code in cur.fetchall()}

def candidates(cur):
    cur.execute(f"""
      select t.id, t.account_id, t.posted_at, t.amount, t.normalized_desc
      from transactions t
      left join tx_splits s on s.transaction_id = t.id
      where s.id is null
        and t.amount < 0
        and t.posted_at >= current_date - interval '{DAYS} days'
    """)
    for row in cur.fetchall():
        yield {
            "id": row[0],
            "account_id": row[1],
            "posted_at": row[2],
            "amount": float(row[3]),
            "desc": (row[4] or "").upper()
        }

def match_rule(tx, rule):
    desc = tx["desc"]
    if not desc:
        return False
    if not any(substr in desc for substr in rule["includes"]):
        return False
    if any(substr in desc for substr in rule["excludes"]):
        return False
    amt = tx["amount"]
    if amt < rule["amount_min"] or amt > rule["amount_max"]:
        return False
    return True

def apply_rules(conn, rules, cat_map):
    n_applied = 0
    with conn.cursor() as cur:
        for tx in candidates(cur):
            for rule in rules:
                if match_rule(tx, rule):
                    cat_id = cat_map.get(rule["category_code"])
                    if not cat_id:
                        continue
                    cur.execute("""
                      insert into tx_splits(transaction_id, category_id, amount, note)
                      values (%s,%s,%s,%s)
                      on conflict do nothing
                    """, (tx["id"], cat_id, tx["amount"], f"rule:{rule['name']}"))
                    n_applied += 1
                    break
    conn.commit()
    print(f"[classify] applied {n_applied} splits")

def main():
    rules = load_rules()
    with psycopg.connect(PG_DSN, autocommit=False) as conn:
        with conn.cursor() as cur:
            cat_map = fetch_categories(cur)
        apply_rules(conn, rules, cat_map)

if __name__ == "__main__":
    main()
