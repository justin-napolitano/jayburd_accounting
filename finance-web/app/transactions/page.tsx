"use client";
import { useState } from "react";
import { TransactionsTable } from "@/components/transactions-table";

export default function TransactionsPage() {
  const [query, setQuery] = useState("");
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Transactions</h1>
        <div className="flex gap-2">
          <input className="input" placeholder="Search..." value={query} onChange={e=>setQuery(e.target.value)} />
        </div>
      </div>
      <TransactionsTable query={query} />
    </div>
  );
}
