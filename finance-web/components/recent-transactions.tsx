"use client";
import { useRecentTransactions } from "@/hooks/useFinance";

export function RecentTransactions() {
  const { data } = useRecentTransactions(6);
  const rows = data || [];
  return (
    <div className="card">
      <div className="mb-2 font-semibold">Recent Transactions</div>
      <table className="table">
        <thead><tr><th>Date</th><th>Description</th><th className="text-right">Amount</th></tr></thead>
        <tbody>
          {rows.map((t:any)=> (
            <tr key={t.id}>
              <td>{t.posted_at?.slice(0,10)}</td>
              <td>{t.description}</td>
              <td className="text-right">{t.amount}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
