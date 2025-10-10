import { KpiGrid } from "@/components/kpi-grid";
import { MonthlySpendChart } from "@/components/monthly-spend-chart";
import { TopCategories } from "@/components/top-categories";
import { RecentTransactions } from "@/components/recent-transactions";

export default function OverviewPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Overview</h1>
      </div>
      <KpiGrid />
      <MonthlySpendChart />
      <div className="grid gap-6 grid-cols-1 lg:grid-cols-2">
        <TopCategories />
        <RecentTransactions />
      </div>
    </div>
  );
}
