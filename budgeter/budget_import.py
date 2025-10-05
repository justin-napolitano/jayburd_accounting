import os, yaml
import psycopg
from calendar import monthrange
from datetime import date

PG_DSN = (
    f"host={os.environ['POSTGRES_HOST']} "
    f"port={os.environ['POSTGRES_PORT']} "
    f"dbname={os.environ['POSTGRES_DB']} "
    f"user={os.environ['POSTGRES_USER']} "
    f"password={os.environ['POSTGRES_PASSWORD']}"
)

BUDGET_FILE = os.getenv("BUDGET_FILE", "/app/config/budgets.yaml")

def month_bounds(ym: str):
    y, m = map(int, ym.split("-"))
    start = date(y, m, 1)
    end = date(y, m, monthrange(y, m)[1])
    return start, end

def main():
    period = os.getenv("BUDGET_PERIOD", "")
    if not period:
        period = date.today().strftime("%Y-%m")

    start, end = month_bounds(period)

    with open(BUDGET_FILE, "r") as f:
        data = yaml.safe_load(f) or {}

    with psycopg.connect(PG_DSN, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("select id, code from categories")
            code_to_id = {code: _id for _id, code in cur.fetchall()}

            for code, amount in data.items():
                cat_id = code_to_id.get(code)
                if not cat_id:
                    print(f"[budget] skip unknown category {code}")
                    continue
                cur.execute("""
                  insert into budgets(category_id, period_start, period_end, amount)
                  values (%s,%s,%s,%s)
                  on conflict (category_id, period_start, period_end)
                  do update set amount = excluded.amount
                """, (cat_id, start, end, float(amount)))

    print(f"[budget] imported budgets for {period}")

if __name__ == "__main__":
    main()
