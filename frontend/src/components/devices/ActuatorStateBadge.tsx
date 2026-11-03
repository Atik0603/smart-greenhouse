import type { DeviceDto } from "../../services/api";

const STYLES: Record<string, string> = {
  idle: "border-slate-300 bg-slate-100 text-slate-700",
  running: "border-emerald-300 bg-emerald-100 text-emerald-800",
  error: "border-red-300 bg-red-100 text-red-800",
  maintenance: "border-amber-300 bg-amber-100 text-amber-800",
  off: "border-slate-700 bg-slate-800 text-slate-100",
};

export function ActuatorStateBadge({ device }: { device: DeviceDto }) {
  if (device.role !== "actuator" || !device.state) return null;

  const tooltip =
    device.allowed_commands.length > 0
      ? `Allowed commands: ${device.allowed_commands.join(", ")}`
      : "No commands available in this state";

  return (
    <span
      title={tooltip}
      className={`rounded-full border px-2 py-0.5 text-xs font-semibold uppercase ${
        STYLES[device.state] ?? STYLES.idle
      }`}
    >
      {device.state}
    </span>
  );
}