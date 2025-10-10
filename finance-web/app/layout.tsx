import "./globals.css";
import { ReactQueryProvider } from "@/components/react-query-provider";
import { Sidebar } from "@/components/sidebar";
import { Topbar } from "@/components/topbar";

export const metadata = { title: "Finance OS", description: "Personal finance dashboard" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ReactQueryProvider>
          <div className="min-h-screen grid grid-cols-[260px_1fr]">
            <Sidebar />
            <div className="flex flex-col">
              <Topbar />
              <main className="container py-6">{children}</main>
            </div>
          </div>
        </ReactQueryProvider>
      </body>
    </html>
  );
}
