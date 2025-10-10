"use client";
import { useSpendByMonth } from "@/hooks/useFinance";

export function TopCategories() {
  const now = new Date();
  const frm = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().slice(0,10);
  const to  = new Date(now.getFullYear(), now.getMonth()+1, 0).toISOString().slice(0,10);
  const { data } = useSpendByMonth(frm, to);
  const rows = (data||[]).slice().sort((a:any,b:any)=> (b.spend||0)-(a.spend||0)).slice(0,8);
  return (
    <div className="card">
      <div className="mb-2 font-semibold">Top Categories (This Month)</div>
      <ul className="space-y-2 text-sm text-neutral-300">
        {rows.map((r:any, i:number)=> (
          <li key={i}>{r.category || "—"} — ${Number(r.spend||0).toFixed(2)}</li>
        ))}
      </ul>
    </div>
  );
}
