"use client";
import { useSpendByMonth } from "@/hooks/useFinance";
import { ResponsiveContainer, BarChart, XAxis, YAxis, Tooltip, Bar } from "recharts";

export function MonthlySpendChart() {
  const now = new Date(); 
  const end = new Date(now.getFullYear(), now.getMonth()+1, 0);
  const start = new Date(now.getFullYear(), now.getMonth()-11, 1);
  const frm = start.toISOString().slice(0,10);
  const to  = end.toISOString().slice(0,10);
  const { data } = useSpendByMonth(frm, to);
  // data is [{month, category, spend}] — sum by month
  const byMonth: Record<string, number> = {};
  (data||[]).forEach((r:any)=> {
    const k = r.month?.slice(0,7) || r.period?.slice(0,7) || r[0];
    const v = Number(r.spend||r.amount||r[2]||0);
    byMonth[k] = (byMonth[k]||0) + v;
  });
  const rows = Object.entries(byMonth).sort().map(([month, spend])=>({ month, spend }));
  return (
    <div className="card">
      <div className="mb-2 font-semibold">Spend by Month</div>
      <div style={{ width: "100%", height: 260 }}>
        <ResponsiveContainer>
          <BarChart data={rows}>
            <XAxis dataKey="month" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="spend" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
