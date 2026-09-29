import { useState, type FormEvent } from "react";
import { createLocationConfig, type LocationConfigResponse } from "../../services/api";
import {
  draftToZoneInput,
  emptyZoneDraft,
  errorMessage,
  findDuplicateZoneName,
  validateZoneDraft,
  type ZoneDraft,
} from "./configHelpers";
import { ZoneFields } from "./ZoneFields";

interface Props {
  onCreated: (config: LocationConfigResponse) => void;
}

export function LocationCreateForm({ onCreated }: Props) {
  const [name, setName] = useState("");
  const [zones, setZones] = useState<ZoneDraft[]>([emptyZoneDraft()]);
  const [submitted, setSubmitted] = useState(false);
  const [saving, setSaving] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  const nameError = name.trim() ? null : "Location name is required";
  const zoneErrors = zones.map(validateZoneDraft);
  const duplicateError = findDuplicateZoneName(zones.map((z) => z.name));
  const hasErrors = Boolean(nameError || duplicateError || zoneErrors.some(Boolean));

  function updateZone(index: number, draft: ZoneDraft) {
    setZones((prev) => prev.map((z, i) => (i === index ? draft : z)));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitted(true);
    setApiError(null);
    if (hasErrors) return;

    setSaving(true);
    try {
      const created = await createLocationConfig({
        location_name: name.trim(),
        zones: zones.map((z) => draftToZoneInput(z)),
      });
      setName("");
      setZones([emptyZoneDraft()]);
      setSubmitted(false);
      onCreated(created);
    } catch (err) {
      setApiError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="font-semibold text-slate-900">New location</h3>

      <label className="block text-xs font-medium text-slate-600">
        Location name
        <input
          className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm text-slate-900 focus:border-emerald-500 focus:outline-none"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Bay A"
          disabled={saving}
        />
      </label>
      {submitted && nameError && <p className="text-xs text-red-600">{nameError}</p>}

      <div className="space-y-3">
        {zones.map((zone, index) => (
          <div key={index} className="rounded-md border border-slate-200 p-3">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Zone {index + 1}
              </span>
              {zones.length > 1 && (
                <button
                  type="button"
                  onClick={() => setZones((prev) => prev.filter((_, i) => i !== index))}
                  className="text-xs text-slate-500 hover:text-red-600"
                  disabled={saving}
                >
                  Remove
                </button>
              )}
            </div>
            <ZoneFields draft={zone} onChange={(d) => updateZone(index, d)} disabled={saving} />
            {submitted && zoneErrors[index] && (
              <p className="mt-2 text-xs text-red-600">{zoneErrors[index]}</p>
            )}
          </div>
        ))}
      </div>
      {submitted && duplicateError && <p className="text-xs text-red-600">{duplicateError}</p>}

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => setZones((prev) => [...prev, emptyZoneDraft()])}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-100"
          disabled={saving}
        >
          + Add zone
        </button>
        <button
          type="submit"
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
          disabled={saving}
        >
          {saving ? "Saving…" : "Create location"}
        </button>
      </div>

      {apiError && <p className="text-sm text-red-600">Server rejected the location: {apiError}</p>}
    </form>
  );
}