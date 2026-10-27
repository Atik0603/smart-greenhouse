import { useEffect, useState, type ReactNode } from "react";
import {
  getLocationOverview,
  listLocations,
  type LocationOverviewDto,
  type LocationSummaryDto,
  type OverviewReadingDto,
  type OverviewZoneDto,
} from "../../services/api";

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</h3>
      {children}
    </div>
  );
}

function Empty({ children }: { children: ReactNode }) {
  return <p className="text-sm italic text-slate-400">{children}</p>;
}

function ZoneCard({ zone }: { zone: OverviewZoneDto }) {
  // Pair each device with its reading from the SAME response (no extra request).
  const readingByDevice = new Map<string, OverviewReadingDto>(
    zone.latest_readings.map((r) => [r.device_id, r]),
  );

  return (
    <Card title={`Zone · ${zone.name}`}>
      <p className="mb-3 text-sm text-slate-600">
        Moisture band{" "}
        <span className="font-medium text-slate-800">
          {zone.moisture_threshold_low.toFixed(2)} – {zone.moisture_threshold_high.toFixed(2)}
        </span>
      </p>

      {zone.devices.length === 0 ? (
        <Empty>No devices assigned to this zone.</Empty>
      ) : (
        <ul className="divide-y divide-slate-100">
          {zone.devices.map((d) => {
            const reading = readingByDevice.get(d.id);
            return (
              <li key={d.id} className="py-2 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-slate-800">{d.display_name ?? d.device_type}</span>
                  <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">{d.role}</span>
                  <span className="text-xs text-slate-400">{d.device_type}</span>
                </div>
                {reading ? (
                  <p className="mt-1 text-slate-600">
                    <span className="font-semibold text-slate-800">
                      {reading.value} {reading.unit}
                    </span>
                    {" · "}tracking {reading.tracking_enabled ? "on" : "off"}
                    {" · "}every {reading.sampling_interval_seconds}s
                    <span className="ml-2 text-xs text-slate-400">
                      {new Date(reading.recorded_at).toLocaleString()}
                    </span>
                  </p>
                ) : (
                  <p className="mt-1 text-xs italic text-slate-400">No reading</p>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}

export default function OverviewPanel() {
  const [locations, setLocations] = useState<LocationSummaryDto[]>([]);
  const [locationId, setLocationId] = useState("");
  const [overview, setOverview] = useState<LocationOverviewDto | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Dropdown options (the existing locations list is allowed for this).
  useEffect(() => {
    listLocations()
      .then((locs) => {
        setLocations(locs);
        if (locs.length > 0) setLocationId(locs[0].id);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  // The ONE call that feeds every card.
  async function loadOverview(id: string) {
    setLoading(true);
    setError(null);
    try {
      setOverview(await getLocationOverview(id));
    } catch (e) {
      setOverview(null);
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  // Selecting a location → one overview fetch.
  useEffect(() => {
    if (locationId) loadOverview(locationId);
  }, [locationId]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <h2 className="mr-auto text-lg font-semibold text-slate-800">Overview</h2>
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
        <button
          onClick={() => loadOverview(locationId)}
          disabled={!locationId || loading}
          className="rounded bg-slate-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>

      {error && (
        <p className="rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>
      )}

      {overview && (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <Card title="Assigned devices">
              <p className="text-sm text-slate-700">
                <span className="text-2xl font-semibold text-slate-900">{overview.device_counts.sensor}</span>{" "}
                sensors
              </p>
              <p className="text-sm text-slate-700">
                <span className="text-2xl font-semibold text-slate-900">{overview.device_counts.actuator}</span>{" "}
                actuators
              </p>
            </Card>

            <Card title="Strategy">
              {overview.strategy_key ? (
                <p className="text-lg font-semibold text-slate-900">{overview.strategy_key}</p>
              ) : (
                <Empty>No strategy saved. Choose one in the Automation section.</Empty>
              )}
            </Card>

            <Card title="Recommendation">
              {overview.last_recommendation ? (
                <>
                  <span
                    className={`rounded-full border px-2 py-0.5 text-xs font-semibold uppercase ${
                      overview.last_recommendation.action === "irrigate"
                        ? "border-sky-300 bg-sky-100 text-sky-800"
                        : "border-slate-300 bg-slate-100 text-slate-700"
                    }`}
                  >
                    {overview.last_recommendation.action}
                  </span>
                  <p className="mt-2 text-sm text-slate-600">{overview.last_recommendation.reason}</p>
                </>
              ) : (
                <Empty>No recommendation without a saved strategy.</Empty>
              )}
            </Card>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            {overview.zones.map((zone) => (
              <ZoneCard key={zone.id} zone={zone} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}