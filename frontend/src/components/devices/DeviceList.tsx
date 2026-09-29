import type { DeviceDto } from "../../services/api";
import type { ZoneGroup } from "../config/useZoneOptions";
import { ZonePicker } from "./ZonePicker";

interface Props {
  devices: DeviceDto[];
  loading: boolean;
  error: string | null;
  zoneGroups?: ZoneGroup[];
  onAssignZone?: (deviceId: string, zoneId: string | null) => Promise<void>;
}

const ROLE_STYLES: Record<DeviceDto["role"], string> = {
  sensor: "bg-sky-100 text-sky-800",
  actuator: "bg-amber-100 text-amber-800",
};

const FAMILY_STYLES: Record<string, string> = {
  simulation: "bg-violet-100 text-violet-800",
  edge: "bg-emerald-100 text-emerald-800",
};

export function DeviceList({ devices, loading, error, zoneGroups, onAssignZone }: Props) {
  if (loading) {
    return <p className="text-sm text-slate-500">Loading devices…</p>;
  }
  if (error) {
    return <p className="text-sm text-red-600">Could not load devices: {error}</p>;
  }
  if (devices.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        No devices in this family yet. Provision a kit to get started.
      </p>
    );
  }

  return (
    <ul className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
      {devices.map((d) => (
        <li key={d.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div className="min-w-0">
            <p className="truncate font-medium text-slate-900">{d.display_name || "(unnamed)"}</p>
            <p className="text-xs text-slate-500">{d.device_type}</p>
          </div>
          <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
            <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${ROLE_STYLES[d.role]}`}>
              {d.role}
            </span>
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                FAMILY_STYLES[d.device_family] ?? "bg-slate-100 text-slate-700"
              }`}
            >
              {d.device_family}
            </span>
            {zoneGroups && onAssignZone && (
              <ZonePicker device={d} groups={zoneGroups} onAssign={onAssignZone} />
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}