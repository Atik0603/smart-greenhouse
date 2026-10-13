import { useEffect, useState } from "react";
import {
  evaluateAutomation,
  getAutomationRule,
  listLocations,
  listStrategies,
  saveAutomationRule,
  type AutomationAction,
  type AutomationEvaluationDto,
  type LocationSummaryDto,
} from "../../services/api";
type Status = { kind: "success" | "error"; text: string } | null;

function ActionBadge({ action }: { action: AutomationAction }) {
  const style =
    action === "irrigate"
      ? "bg-sky-100 text-sky-800 border-sky-300"
      : "bg-slate-100 text-slate-700 border-slate-300";
  return (
    <span className={`rounded-full border px-2 py-0.5 text-xs font-semibold uppercase ${style}`}>
      {action}
    </span>
  );
}

export default function StrategyPanel() {
  const [locations, setLocations] = useState<LocationSummaryDto[]>([]);
  const [strategies, setStrategies] = useState<string[]>([]);
  const [locationId, setLocationId] = useState("");
  const [savedKey, setSavedKey] = useState<string | null>(null);
  const [selectedKey, setSelectedKey] = useState("");
  const [evaluation, setEvaluation] = useState<AutomationEvaluationDto | null>(null);
  const [status, setStatus] = useState<Status>(null);
  const [busy, setBusy] = useState(false);

  // On first render: load locations and the known strategy keys.
  useEffect(() => {
    Promise.all([listLocations(), listStrategies()])
      .then(([locs, keys]) => {
        setLocations(locs);
        setStrategies(keys);
        if (locs.length > 0) setLocationId(locs[0].id);
      })
      .catch((e: Error) => setStatus({ kind: "error", text: e.message }));
  }, []);

  // Whenever the location changes: load its saved strategy.
  useEffect(() => {
    if (!locationId) return;
    setEvaluation(null);
    setStatus(null);
    getAutomationRule(locationId)
      .then((rule) => {
        setSavedKey(rule?.strategy_key ?? null);
        setSelectedKey(rule?.strategy_key ?? "");
      })
      .catch((e: Error) => setStatus({ kind: "error", text: e.message }));
  }, [locationId]);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setStatus(null);
    try {
      await action();
    } catch (e) {
      setStatus({ kind: "error", text: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusy(false);
    }
  }

  const save = () =>
    run(async () => {
      const rule = await saveAutomationRule(locationId, selectedKey);
      setSavedKey(rule.strategy_key);
      setEvaluation(null); // old result belonged to the previous strategy
      setStatus({ kind: "success", text: `Saved strategy "${rule.strategy_key}"` });
    });

  const evaluate = () =>
    run(async () => {
      setEvaluation(await evaluateAutomation(locationId));
    });

  const unsaved = selectedKey !== "" && selectedKey !== savedKey;

  return (
    <div className="space-y-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="text-lg font-semibold text-slate-800">Automation strategy</h2>

      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col text-sm">
          <span className="mb-1 font-medium text-slate-600">Location</span>
          <select
            value={locationId}
            onChange={(e) => setLocationId(e.target.value)}
            className="rounded border border-slate-300 px-2 py-1"
          >
            {locations.map((l) => (
              <option key={l.id} value={l.id}>
                {l.name}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col text-sm">
          <span className="mb-1 font-medium text-slate-600">Strategy</span>
          <select
            value={selectedKey}
            onChange={(e) => setSelectedKey(e.target.value)}
            className="rounded border border-slate-300 px-2 py-1"
          >
            <option value="" disabled>
              Not set
            </option>
            {strategies.map((key) => (
              <option key={key} value={key}>
                {key}
              </option>
            ))}
          </select>
        </label>

        <button
          onClick={save}
          disabled={busy || !locationId || !unsaved}
          className="rounded bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Save
        </button>
        <button
          onClick={evaluate}
          disabled={busy || !locationId}
          className="rounded bg-sky-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy ? "Working…" : "Evaluate"}
        </button>
      </div>

      <p className="text-sm text-slate-500">
        Saved strategy: <span className="font-medium text-slate-700">{savedKey ?? "not set"}</span>
        {unsaved && (
          <span className="ml-2 text-amber-600">
            Unsaved change: Evaluate uses the saved strategy.
          </span>
        )}
      </p>

      {status && (
        <p
          className={`rounded border px-3 py-2 text-sm ${
            status.kind === "success"
              ? "border-emerald-300 bg-emerald-50 text-emerald-800"
              : "border-red-300 bg-red-50 text-red-800"
          }`}
        >
          {status.text}
        </p>
      )}

      {evaluation && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <ActionBadge action={evaluation.action} />
            <span className="text-sm text-slate-700">{evaluation.reason}</span>
            <span className="ml-auto text-xs text-slate-400">
              strategy: {evaluation.strategy_key}
            </span>
          </div>

          <ul className="divide-y divide-slate-100 rounded border border-slate-200">
            {evaluation.zones.map((z) => (
              <li key={z.zone_id} className="flex flex-wrap items-center gap-3 px-3 py-2 text-sm">
                <span className="w-24 font-medium text-slate-800">{z.zone_name}</span>
                <span className="w-28 text-slate-500">
                  moisture: {z.moisture === null ? "–" : z.moisture.toFixed(2)}
                </span>
                <ActionBadge action={z.action} />
                <span className="text-slate-600">{z.reason}</span>
                {z.score !== null && z.score > 0 && (
                  <span className="ml-auto text-xs text-sky-700">urgency {z.score}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}