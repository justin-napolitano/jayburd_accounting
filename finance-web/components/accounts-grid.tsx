"use client";
import { useAccounts } from "@/hooks/useFinance";

export function AccountsGrid() {
  const { data } = useAccounts();
  const rows = data || [];
  return (
    <div className="grid gap-4 grid-cols-1 md:grid-cols-2 xl:grid-cols-3">
      {rows.map((a:any)=> (
        <div key={a.id} className="card">
          <div className="text-lg font-semibold">{a.name}</div>
          <div className="text-neutral-400 text-sm">{a.institution || "Institution"} ••••{a.mask || "—"}</div>
          <div className="mt-2 text-sm text-neutral-400 capitalize">{a.type} • {a.currency}</div>
          <div className="mt-3 flex gap-2">
            <a href="/transactions" className="btn">View tx</a>
            <button className="btn">Sync now</button>
          </div>
        </div>
      ))}
    </div>
  );
}
