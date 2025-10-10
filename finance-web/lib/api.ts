export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8010";

async function req(path: string) {
  const r = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`API ${r.status}: ${path}`);
  return r.json();
}

export const api = {
  accounts: () => req("/accounts"),
  transactions: (qs: string) => req(`/transactions${qs ? "?" + qs : ""}`),
  spendMonthly: (qs: string) => req(`/spend/monthly?${qs}`),
  budgetStatus: (period: string) => req(`/budget/status?period=${encodeURIComponent(period)}`),
};
