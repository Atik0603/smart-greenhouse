import type { DeviceFamily } from "../../services/api";

const FAMILIES: { key: DeviceFamily; label: string }[] = [
  { key: "simulation", label: "Simulation" },
  { key: "edge", label: "Edge" },
];

interface Props {
  value: DeviceFamily;
  onChange: (family: DeviceFamily) => void;
  disabled?: boolean;
}

export function DeviceFamilySwitcher({ value, onChange, disabled = false }: Props) {
  return (
    <div
      className="inline-flex overflow-hidden rounded-lg border border-slate-300"
      role="group"
      aria-label="Device family"
    >
      {FAMILIES.map((f) => {
        const active = f.key === value;
        return (
          <button
            key={f.key}
            type="button"
            disabled={disabled}
            aria-pressed={active}
            onClick={() => onChange(f.key)}
            className={`px-4 py-2 text-sm font-medium transition disabled:opacity-50 ${
              active ? "bg-emerald-600 text-white" : "bg-white text-slate-700 hover:bg-slate-100"
            }`}
          >
            {f.label}
          </button>
        );
      })}
    </div>
  );
}