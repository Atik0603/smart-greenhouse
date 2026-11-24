import { useEffect, useState } from "react";
import {
  getLocationConfig,
  listAlerts,
  listLocations,
  type AlertDto,
  type AlertSeverity,
  type LocationSummaryDto,
  type ZoneReadDto,
} from "../../services/api";
import { subscribeRealtime } from "../../services/realtime";

const POLL_MS = 5000;

const SEVERITY_STYLES: Record<AlertSeverity, string> = {
  info: "border-sky-300 bg-sky-100 text-sky-800",
  warning: "border-amber-300 bg-amber-100 text-amber-800",
  critical: "border-red-300 bg-red-100 text-red-800",
};

export default function EventFeed() {
  const [locations, setLocations] = useState<LocationSummaryDto[]>([]);
  const [zones, setZones] = useState<ZoneReadDto[]>([]);
  const [locationId, setLocationId] = useState("");
  const [zoneId, setZoneId] = useState("");
  const [alerts, setAlerts] = useState<AlertDto[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  // Location options for the filter (loaded once).
  useEffect(() => {
    listLocations()
      .then(setLocations)
      .catch((e: Error) => setError(e.message));
  }, []);

  // Zone options follow the chosen location.
  useEffect(() => {
    setZoneId("");
    setZones([]);
    if (!locationId) return;
    getLocationConfig(locationId)
      .then((config) => setZones(config.zones))
      .catch((e: Error) => setError(e.message));
  }, [locationId]);

  // Poll the alerts every 5 seconds for the current filters.
  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const rows = await listAlerts({
          locationId: locationId || undefined,
          zoneId: zoneId || undefined,
        });
        if (!cancelled) {
          setAlerts(rows);
          setError(null);
          setLastUpdated(new Date());
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    }

    load();
    const timer = setInterval(load, POLL_MS);
    const unsubscribe = subscribeRealtime(() => load()); // no-op until Phase 12

    return () => {
      cancelled = true;
      clearInterval(timer);
      unsubscribe();
    };
  }, [locationId, zoneId]);

  const zoneName = (id: string | null) =>
    id === null ? "unassigned" : zones.find((z) => z.id === id)?.name ?? id.slice(0, 8);

  return (
    <div className="space-y-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-end gap-3">
        <div className="mr-auto">
          <h2 className="text-lg font-semibold text-slate-800">Event feed</h2>
          <p className="text-xs text-slate-400">
            Active alerts · refreshes every 5 s
            {lastUpdated && ` · updated ${lastUpdated.toLocaleTimeString()}`}
          </p>
        </div>

        <label className="flex flex-col text-sm">
          <span className="mb-1 font-medium text-slate-600">Location</span>
          <select
            value={locationId}
            onChange={(e) => setLocationId(e.target.value)}
            className="rounded border border-slate-300 px-2 py-1"
          >
            <option value="">All locations</option>
            {locations.map((l) => (
              <option key={l.id} value={l.id}>
                {l.name}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col text-sm">
          <span className="mb-1 font-medium text-slate-600">Zone</span>
          <select
            value={zoneId}
            onChange={(e) => setZoneId(e.target.value)}
            disabled={!locationId}
            className="rounded border border-slate-300 px-2 py-1 disabled:opacity-50"
          >
            <option value="">All zones</option>
            {zones.map((z) => (
              <option key={z.id} value={z.id}>
                {z.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      {error && (
        <p className="rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>
      )}

      {alerts.length === 0 ? (
        <p className="text-sm italic text-slate-400">No active alerts.</p>
      ) : (
        <ul className="divide-y divide-slate-100 rounded border border-slate-200">
          {alerts.map((a) => (
            <li key={a.id} className="flex flex-wrap items-center gap-3 px-3 py-2 text-sm">
              <span
                className={`rounded-full border px-2 py-0.5 text-xs font-semibold uppercase ${SEVERITY_STYLES[a.severity]}`}
              >
                {a.severity}
              </span>
              <span className="font-medium text-slate-800">{a.message}</span>
              <span className="font-mono text-xs text-slate-400">{a.event_type}</span>
              {locationId && <span className="text-xs text-slate-500">zone: {zoneName(a.zone_id)}</span>}
              <span className="ml-auto whitespace-nowrap text-xs text-slate-400">
                {new Date(a.created_at).toLocaleString()}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}