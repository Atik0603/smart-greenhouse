import { useEffect, useState } from "react";
import {
  listSensorReadings,
  readSensorNow,
  updateSampling,
  type DeviceDto,
  type ReadingDto,
  type ReadingSource,
} from "../../services/api";

// TEMPORARY: poll the latest stored reading every few seconds.
// Phase 12 replaces this poll with a WebSocket push (reading.created).
const POLL_MS = 3000;
const MIN_INTERVAL_SECONDS = 5;

const SOURCE_STYLES: Record<ReadingSource, string> = {
  simulation: "bg-violet-100 text-violet-800",
  vendor: "bg-amber-100 text-amber-800",
  mqtt: "bg-sky-100 text-sky-800",
};

const errorMessage = (e: unknown) => (e instanceof Error ? e.message : String(e));

function formatValue(r: ReadingDto): string {
  const digits = r.unit === "vwc" ? 3 : 0;
  return `${r.value.toFixed(digits)} ${r.unit}`;
}

interface Props {
  device: DeviceDto;
  onDeviceUpdated: (device: DeviceDto) => void;
}

export function SensorReadingPanel({ device, onDeviceUpdated }: Props) {
  // undefined = still loading, null = no readings stored yet
  const [latest, setLatest] = useState<ReadingDto | null | undefined>(undefined);
  const [pollError, setPollError] = useState<string | null>(null);

  const [reading, setReading] = useState(false);
  const [readError, setReadError] = useState<string | null>(null);

  const [intervalDraft, setIntervalDraft] = useState(String(device.sampling_interval_seconds));
  const [trackingDraft, setTrackingDraft] = useState(device.tracking_enabled);
  const [saving, setSaving] = useState(false);
  const [samplingError, setSamplingError] = useState<string | null>(null);
  const [samplingSaved, setSamplingSaved] = useState(false);

  // Keep the form in sync if the device is updated from elsewhere (e.g. after a save).
  useEffect(() => {
    setIntervalDraft(String(device.sampling_interval_seconds));
    setTrackingDraft(device.tracking_enabled);
  }, [device.sampling_interval_seconds, device.tracking_enabled]);

  // TEMPORARY poll (see comment at the top). Loads from the DB, so a refresh still shows the last value.
  useEffect(() => {
    let cancelled = false;

    async function loadLatest() {
      try {
        const rows = await listSensorReadings(device.id, 1);
        if (!cancelled) {
          setLatest(rows[0] ?? null);
          setPollError(null);
        }
      } catch (e) {
        if (!cancelled) setPollError(errorMessage(e));
      }
    }

    loadLatest();
    const timer = window.setInterval(loadLatest, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [device.id]);

  async function handleReadNow() {
    setReading(true);
    setReadError(null);
    try {
      setLatest(await readSensorNow(device.id));
    } catch (e) {
      setReadError(errorMessage(e));
    } finally {
      setReading(false);
    }
  }

  async function handleSaveSampling() {
    const seconds = Number(intervalDraft);
    if (!Number.isInteger(seconds) || seconds < MIN_INTERVAL_SECONDS) {
      setSamplingError(`Interval must be a whole number of at least ${MIN_INTERVAL_SECONDS} seconds`);
      return;
    }
    setSaving(true);
    setSamplingError(null);
    setSamplingSaved(false);
    try {
      const updated = await updateSampling(device.id, seconds, trackingDraft);
      onDeviceUpdated(updated);
      setSamplingSaved(true);
    } catch (e) {
      setSamplingError(errorMessage(e));
    } finally {
      setSaving(false);
    }
  }

  const changed =
    intervalDraft !== String(device.sampling_interval_seconds) ||
    trackingDraft !== device.tracking_enabled;

  return (
    <div className="mt-3 space-y-3 rounded-md border border-slate-200 bg-slate-50 p-3">
      {/* Latest value + source */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          {latest === undefined ? (
            <p className="text-sm text-slate-500">Loading latest reading…</p>
          ) : latest === null ? (
            <p className="text-sm text-slate-500">No readings yet</p>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-lg font-semibold text-slate-900">{formatValue(latest)}</span>
              <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${SOURCE_STYLES[latest.source]}`}>
                {latest.source}
              </span>
              <span className="text-xs text-slate-500">
                {new Date(latest.recorded_at).toLocaleTimeString()}
              </span>
            </div>
          )}
          {pollError && <p className="text-xs text-red-600">Could not refresh: {pollError}</p>}
        </div>
        <button
          type="button"
          onClick={handleReadNow}
          disabled={reading}
          className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
        >
          {reading ? "Reading…" : "Read now"}
        </button>
      </div>
      {readError && <p className="text-xs text-red-600">{readError}</p>}

      {/* Sampling controls */}
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-xs font-medium text-slate-600">
          Interval (seconds)
          <input
            type="number"
            min={MIN_INTERVAL_SECONDS}
            step={1}
            value={intervalDraft}
            onChange={(e) => {
              setIntervalDraft(e.target.value);
              setSamplingSaved(false);
            }}
            disabled={saving}
            className="mt-1 block w-24 rounded-md border border-slate-300 px-2 py-1 text-sm text-slate-900 focus:border-emerald-500 focus:outline-none"
          />
        </label>
        <label className="flex items-center gap-2 pb-1.5 text-xs font-medium text-slate-600">
          <input
            type="checkbox"
            checked={trackingDraft}
            onChange={(e) => {
              setTrackingDraft(e.target.checked);
              setSamplingSaved(false);
            }}
            disabled={saving}
            className="h-4 w-4 accent-emerald-600"
          />
          Tracking
        </label>
        <button
          type="button"
          onClick={handleSaveSampling}
          disabled={saving || !changed}
          className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-white disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save"}
        </button>
        {samplingSaved && <span className="pb-1.5 text-xs text-emerald-700">Saved</span>}
      </div>
      {samplingError && <p className="text-xs text-red-600">{samplingError}</p>}
    </div>
  );
}