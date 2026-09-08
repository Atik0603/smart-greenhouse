import type { ReactNode } from "react";
import { HealthStatus } from "./HealthStatus";

export function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="flex items-center justify-between border-b bg-white px-6 py-4">
        <h1 className="text-lg font-semibold">Smart Greenhouse</h1>
        <HealthStatus />
      </header>
      <main className="p-6">{children}</main>
    </div>
  );
}