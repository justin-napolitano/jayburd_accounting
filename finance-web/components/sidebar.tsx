import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, CreditCard, Wallet, Settings, Calendar } from "lucide-react";
import clsx from "clsx";

const links = [
  { href: "/", label: "Overview", icon: Home },
  { href: "/transactions", label: "Transactions", icon: CreditCard },
  { href: "/budgets", label: "Budgets", icon: Calendar },
  { href: "/accounts", label: "Accounts", icon: Wallet },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="h-screen bg-neutral-950 border-r border-neutral-900 p-4">
      <div className="text-lg font-semibold mb-6">Finance</div>
      <nav className="space-y-1">
        {links.map(({ href, label, icon: Icon }) => (
          <Link key={href} href={href} className={clsx(
            "flex items-center gap-2 px-3 py-2 rounded-xl hover:bg-neutral-900",
            pathname === href && "bg-neutral-900 text-white"
          )}>
            <Icon size={18} />
            <span>{label}</span>
          </Link>
        ))}
      </nav>
    </aside>
  );
}
