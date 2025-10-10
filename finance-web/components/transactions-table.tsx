"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function TransactionsTable({ query }: { query?: string }) {
  const params = new URLSearchParams();
  params.set("limit","50");
  if (query) params.set("q", query);
  const { data, isLoading } = useQuery({
    queryKey: ["transactions", params.toString()],
    queryFn: () => api.transactions(params.toString()),
    staleTime: 30_000
  });
  const rows = data || [];
  return (
    <div className="card">
      <table className="table">
        <thead>
          <tr>
            <th>Date</th><th>Account</th><th>Description</th><th>Category</th><th className="text-right">Amount</th>
          </tr>
        </thead>
        <tbody>
          {isLoading && <tr><td colSpan={5}>Loading…</td></tr>}
          {rows.map((t:any) => (
            <tr key={t.id}>
              <td>{t.posted_at?.slice(0,10)}</td>
              <td>{t.account_id}</td>
              <td>{t.description}</td>
              <td>{t.categories || "—"}</td>
              <td className="text-right">{t.amount}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
