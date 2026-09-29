import { useState, type ChangeEvent } from "react";
import type { DeviceDto } from "../../services/api";
import { errorMessage } from "../config/configHelpers";
import { zoneLabel, type ZoneGroup } from "../config/useZoneOptions";

interface Props {
  device: DeviceDto;
  groups: ZoneGroup[];
  onAssign: (deviceId: string, zoneId: string | null) => Promise<void>;
}

export function ZonePicker({ device, groups, onAssign }: Props) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const knownZone = groups.flatMap((g) => g.zones).find((z) => z.zoneId === device.zone_id);

  async function handleChange(e: ChangeEvent<HTMLSelectElement>) {
    const value = e.target.value;
    setSaving(true);
    setError(null);
    try {
      await onAssign(device.id, value === "" ? null : value);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <select
        value={device.zone_id ?? ""}
        onChange={handleChange}
        disabled={saving}
        aria-label={`Zone for ${device.display_name}`}
        className="max-w-[16rem] rounded-md border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700 focus:border-emerald-500 focus:outline-none disabled:opacity-50"
      >
        <option value="">Unassigned</option>
        {groups.map((g) => (
          <optgroup key={g.locationId} label={g.locationName}>
            {g.zones.map((z) => (
              <option key={z.zoneId} value={z.zoneId}>
                {zoneLabel(z)}
              </option>
            ))}
          </optgroup>
        ))}
        {device.zone_id && !knownZone && <option value={device.zone_id}>Unknown zone</option>}
      </select>
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  );
}