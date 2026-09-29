import { useState } from "react";
import { deleteZone, updateZone, type DeviceDto, type ZoneReadDto } from "../../services/api";
import {
  draftToZoneInput,
  errorMessage,
  validateZoneDraft,
  zoneToDraft,
  type ZoneDraft,
} from "./configHelpers";
import { ZoneFields } from "./ZoneFields";

interface Props {
  locationId: string;
  zone: ZoneReadDto;
  devices: DeviceDto[] | undefined;
  otherZoneNames: string[];
  onChanged: () => void;
}

export function ZoneEditor({ locationId, zone, devices, otherZoneNames, onChanged }: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<ZoneDraft>(() => zoneToDraft(zone));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function startEdit() {
    setDraft(zoneToDraft(zone));
    setError(null);
    setEditing(true);
  }

  async function handleSave() {
    const problem =
      validateZoneDraft(draft) ??
      (otherZoneNames.some((n) => n.toLowerCase() === draft.name.trim().toLowerCase())
        ? `Zone name "${draft.name.trim()}" already exists in this location`
        : null);
    if (problem) {
      setError(problem);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await updateZone(locationId, zone.id, draftToZoneInput(draft, zone.schedule));
      setEditing(false);
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    if (!window.confirm(`Delete zone "${zone.name}"? Devices in it become unassigned.`)) return;
    setBusy(true);
    setError(null);
    try {
      await deleteZone(locationId, zone.id);
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const waterAt = typeof zone.schedule.water_at === "string" ? zone.schedule.water_at : null;

  return (
    <li className="space-y-2 px-4 py-3">
      {editing ? (
        <>
          <ZoneFields draft={draft} onChange={setDraft} disabled={busy} />
          <div className="flex gap-2">
            <button type="button" onClick={handleSave} disabled={busy} className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50">
              {busy ? "Saving…" : "Save"}
            </button>
            <button type="button" onClick={() => setEditing(false)} disabled={busy} className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-100">
              Cancel
            </button>
          </div>
        </>
      ) : (
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="font-medium text-slate-900">{zone.name}</p>
            <p className="text-xs text-slate-500">
              Moisture {zone.moisture_threshold_low} – {zone.moisture_threshold_high}
              {waterAt ? ` · waters at ${waterAt}` : " · no schedule"}
            </p>
            <p className="mt-1 text-xs text-slate-600">
              {devices === undefined
                ? "Loading devices…"
                : devices.length === 0
                  ? "No devices assigned"
                  : `Devices: ${devices.map((d) => d.display_name || d.device_type).join(", ")}`}
            </p>
          </div>
          <div className="flex shrink-0 gap-2">
            <button type="button" onClick={startEdit} disabled={busy} className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-100">
              Edit
            </button>
            <button type="button" onClick={handleDelete} disabled={busy} className="rounded-md border border-red-200 px-3 py-1.5 text-sm text-red-700 hover:bg-red-50 disabled:opacity-50">
              Delete
            </button>
          </div>
        </div>
      )}
      {error && <p className="text-xs text-red-600">{error}</p>}
    </li>
  );
}