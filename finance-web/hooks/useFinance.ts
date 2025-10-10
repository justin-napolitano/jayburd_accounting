"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { currentPeriodYYYYMM } from "@/lib/date";

export function useAccounts() {
  return useQuery({ queryKey: ["accounts"], queryFn: api.accounts, staleTime: 60_000 });
}

export function useRecentTransactions(limit = 6) {
  const qs = `limit=${limit}`;
  return useQuery({ queryKey: ["transactions", qs], queryFn: () => api.transactions(qs), staleTime: 30_000 });
}

export function useTransactions(params: Record<string,string>) {
  const qs = new URLSearchParams(params).toString();
  return useQuery({ queryKey: ["transactions", qs], queryFn: () => api.transactions(qs), staleTime: 30_000 });
}

export function useSpendByMonth(frm: string, to: string) {
  const qs = `frm=${frm}&to=${to}`;
  return useQuery({ queryKey: ["spend-monthly", qs], queryFn: () => api.spendMonthly(qs), staleTime: 60_000 });
}

export function useBudget(period?: string) {
  const p = period || currentPeriodYYYYMM();
  return useQuery({ queryKey: ["budget", p], queryFn: () => api.budgetStatus(p), staleTime: 60_000 });
}
