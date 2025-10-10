"use client";
import { useRouter } from "next/navigation";

export function Topbar() {
  const r = useRouter();
  return (
    <div className="sticky top-0 z-20 bg-neutral-950/80 backdrop-blur border-b border-neutral-900">
      <div className="container flex items-center justify-between py-3">
        <input
          className="input w-full max-w-md"
          placeholder="Search transactions…"
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              const q = (e.target as HTMLInputElement).value;
              r.push(`/transactions?query=${encodeURIComponent(q)}`);
            }
          }}
        />
        <button className="btn" onClick={()=>r.refresh()}>Sync Now</button>
      </div>
    </div>
  );
}
