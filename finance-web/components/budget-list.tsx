"use client";
import { useBudget } from "@/hooks/useFinance";

function pct(spent:number, budget:number){ return budget ? Math.min(100, Math.round(100*spent/budget)) : 0; }

export function BudgetList() {
  const now = new Date(); const period = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,"0")}`;
  const { data } = useBudget(period);
  const rows = (data || []) as any[];

  return (
    <div className="card">
      <div className="mb-2 font-semibold">Budgets — {period}</div>
      <div className="space-y-3">
        {rows.length === 0 && <div className="text-neutral-400 text-sm">No budget data.</div>}
        {rows.map((r:any)=> {
          const name = r.category || r.code || "—";
          const spent = Math.abs(Number(r.actual_spend ?? r.spent ?? 0));
          const budget = Number(r.budget ?? 0);
          const remaining = Number(r.remaining ?? (budget - spent));
          const p = pct(spent, budget);
          return (
            <div key={r.category_id} className="space-y-1">
              <div className="flex justify-between text-sm">
                <div>{name}</div>
                <div>${spent.toFixed(2)} / ${budget.toFixed(2)} <span className="text-neutral-400 ml-2">{remaining >= 0 ? `-${remaining.toFixed(2)} left` : `+${Math.abs(remaining).toFixed(2)} over`}</span></div>
              </div>
              <div className="h-2 bg-neutral-800 rounded-xl overflow-hidden">
                <div className={"h-full " + (remaining < 0 ? "bg-red-500" : "bg-indigo-500")} style={{ width: p + "%" }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
