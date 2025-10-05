from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional, List
import os, psycopg
from datetime import datetime, date
from dateutil import parser as dparse

DB_DSN = (
    f"host={os.environ['POSTGRES_HOST']} "
    f"port={os.environ['POSTGRES_PORT']} "
    f"dbname={os.environ['POSTGRES_DB']} "
    f"user={os.environ.get('POSTGRES_RO_USER', os.environ['POSTGRES_USER'])} "
    f"password={os.environ.get('POSTGRES_RO_PASSWORD', os.environ['POSTGRES_PASSWORD'])}"
)

app = FastAPI(title="Finance OS API", version="0.1.0")

def rows(q, cur):
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in q]

@app.get("/healthz")
def healthz():
    try:
        with psycopg.connect(DB_DSN, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("select 1")
                cur.fetchone()
        return {"status":"ok"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@app.get("/accounts")
def accounts():
    with psycopg.connect(DB_DSN) as conn, conn.cursor() as cur:
        cur.execute("""
          select a.id, a.name, a.type, a.currency, a.mask, i.name as institution
          from accounts a left join institutions i on i.id=a.institution_id
          where a.is_active = true
          order by i.name nulls last, a.name
        """)
        return rows(cur.fetchall(), cur)

@app.get("/spend/monthly")
def spend_monthly(frm: Optional[str]=Query(None), to: Optional[str]=Query(None)):
    where=[]
    params=[]
    if frm:
        where.append("month >= date_trunc('month', %s::date)")
        params.append(frm)
    if to:
        where.append("month <= date_trunc('month', %s::date)")
        params.append(to)
    sql = "select * from v_monthly_spend"
    if where:
        sql += " where " + " and ".join(where)
    sql += " order by month desc, spend desc"
    with psycopg.connect(DB_DSN) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return rows(cur.fetchall(), cur)

@app.get("/budget/status")
def budget_status(period: Optional[str]=Query(None, description="YYYY-MM")):
    where=[]
    params=[]
    if period:
        where.append("period_start = date_trunc('month', %s::date)")
        params.append(period + "-01")
    sql = "select * from v_budget_status"
    if where:
        sql += " where " + " and ".join(where)
    sql += " order by category"
    with psycopg.connect(DB_DSN) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return rows(cur.fetchall(), cur)

@app.get("/transactions")
def transactions(
    account_id: Optional[int]=None,
    frm: Optional[str]=None,
    to: Optional[str]=None,
    uncategorized: bool=False,
    limit: int=Query(100, ge=1, le=1000),
    offset: int=Query(0, ge=0)
):
    where=[]
    params=[]
    if account_id:
        where.append("t.account_id=%s"); params.append(account_id)
    if frm:
        where.append("t.posted_at >= %s::date"); params.append(frm)
    if to:
        where.append("t.posted_at <= %s::date"); params.append(to)
    if uncategorized:
        where.append("not exists (select 1 from tx_splits s where s.transaction_id=t.id)")

    sql = """
      select t.id, t.posted_at, t.amount, t.currency, t.description, t.normalized_desc,
             t.account_id, t.external_tx_id,
             coalesce(string_agg(c.code, ',' order by c.code) filter (where c.code is not null), '') as categories
      from transactions t
      left join tx_splits s on s.transaction_id=t.id
      left join categories c on c.id=s.category_id
    """
    if where:
        sql += " where " + " and ".join(where)
    sql += " group by t.id order by t.posted_at desc, t.id desc limit %s offset %s"
    params.extend([limit, offset])

    with psycopg.connect(DB_DSN) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return rows(cur.fetchall(), cur)

