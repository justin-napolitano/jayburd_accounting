import { BudgetList } from "@/components/budget-list";

export default function BudgetsPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Budgets</h1>
      <BudgetList />
    </div>
  );
}
