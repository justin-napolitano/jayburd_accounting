"use client";
import { useSpendByMonth, useTransactions } from "@/hooks/useFinance";
import { fmtMoney } from "@/lib/date";

export function KpiGrid() {
  const now = new Date();
  const frm = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().slice(0,10);
  const to  = new Date(now.getFullYear(), now.getMonth()+1, 0).toISOString().slice(0,10);
  const { data: spendData } = useSpendByMonth(frm, to);
  const { data: txData } = useTransactions({ frm, to, limit: "1000" });

  const thisMonthSpend = (spendData||[]).reduce((sum:any, row:any)=> sum + (Number(row.spend)||0), 0);
  const daysSoFar = now.getDate();
  const avgDaily = daysSoFar ? thisMonthSpend / daysSoFar : 0;

  const uncategorized = (txData||[]).filter((t:any)=> !t.categories || t.categories.trim()==="").length;

  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
      <div className="kpi">
        <div className="text-sm text-neutral-400">This Month Spend</div>
        <div className="text-2xl font-semibold">{fmtMoney(thisMonthSpend)}</div>
      </div>
      <div className="kpi">
        <div className="text-sm text-neutral-400">Avg Daily Spend</div>
        <div className="text-2xl font-semibold">{fmtMoney(avgDaily)}</div>
      </div>
      <div className="kpi">
        <div className="text-sm text-neutral-400">Uncategorized</div>
        <div className="text-2xl font-semibold">{uncategorized}</div>
      </div>
      <div className="kpi">
        <div className="text-sm text-neutral-400">Net New Tx (30d)</div>
        <div className="text-2xl font-semibold">{(txData||[]).length}</div>
      </div>
    </div>
  );
}
