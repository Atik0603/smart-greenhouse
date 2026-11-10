import { useEffect, useState } from "react";
import { listExecutions, type ExecutionDto } from "../../services/api";

export default function ExecutionLog() {
  const [rows, setRows] = useState<ExecutionDto[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setRows(await listExecutions(20));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="space-y-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-slate-800">Actuator execution log</h2>
        <button
          type="button"
          onClick={load}
          disabled={loading}
          className="rounded bg-slate-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>

      <div className="rounded border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
        Every command sent to an actuator is recorded here. The command name is not validated in
        this phase, so any command succeeds until the actuator has been <b>running</b> for 30
        minutes. A successful row has no message and the policy <code>logging</code>. A blocked
        row shows <i>Max run time exceeded</i> with the policies <code>maxRunTime</code> and{" "}
        <code>logging</code>; the actuator was never called.
      </div>

      {error && (
        <p className="rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>
      )}

      {!error && rows.length === 0 && !loading && (
        <p className="text-sm italic text-slate-400">No executions yet.</p>
      )}

      {rows.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
              <tr>
                <th className="py-2 pr-3">Time</th>
                <th className="py-2 pr-3">Device</th>
                <th className="py-2 pr-3">Result</th>
                <th className="py-2 pr-3">Policies</th>
                <th className="py-2">Message</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((r) => (
                <tr key={r.id}>
                  <td className="whitespace-nowrap py-2 pr-3 text-slate-600">
                    {new Date(r.created_at).toLocaleString()}
                  </td>
                  <td className="py-2 pr-3 font-mono text-xs text-slate-500" title={r.device_id}>
                    {r.device_id.slice(0, 8)}
                  </td>
                  <td className="py-2 pr-3">
                    <span
                      className={`rounded-full border px-2 py-0.5 text-xs font-semibold uppercase ${
                        r.success
                          ? "border-emerald-300 bg-emerald-100 text-emerald-800"
                          : "border-red-300 bg-red-100 text-red-800"
                      }`}
                    >
                      {r.success ? "success" : "blocked"}
                    </span>
                  </td>
                  <td className="py-2 pr-3">
                    <div className="flex flex-wrap gap-1">
                      {r.policy_applied.map((p) => (
                        <span key={p} className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-700">
                          {p}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="py-2 text-slate-600">{r.message ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}