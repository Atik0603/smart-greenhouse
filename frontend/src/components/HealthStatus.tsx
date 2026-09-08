import { useEffect, useState } from "react";
import { getHealth, type HealthResponse } from "../services/api";

export function HealthStatus() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setError(true));
  }, []);

  const color = error || health?.status !== "ok" ? "bg-red-500" : "bg-green-500";
  const label = error ? "unreachable" : health?.status ?? "checking...";

  return (
    <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm text-white ${color}`}>
      <span className="h-2 w-2 rounded-full bg-white/80" />
      API: {label}
    </span>
  );
}