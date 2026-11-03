import { useState } from "react";
import { transitionActuator, type DeviceDto } from "../../services/api";

const TARGETS = ["off", "idle", "running", "maintenance", "error"];

interface Props {
  device: DeviceDto;
  onDeviceUpdated: (device: DeviceDto) => void;
}

export function ActuatorTransitionDemo({ device, onDeviceUpdated }: Props) {
  const [target, setTarget] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  if (device.role !== "actuator") return null;

  async function go() {
    if (!target) return;
    setBusy(true);
    setMessage(null);
    try {
      const result = await transitionActuator(device.id, target);
      // The backend owns the rules; the UI only shows the new state it returned.
      onDeviceUpdated({ ...device, state: result.state, allowed_commands: result.allowed_commands });
      setMessage({ ok: true, text: `Now ${result.state}` });
      setTarget("");
    } catch (e) {
      // An illegal move comes back as a 409 with the backend's explanation.
      setMessage({ ok: false, text: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
      <span>Demo transition (Phase 10 adds real commands):</span>
      <select
        value={target}
        onChange={(e) => setTarget(e.target.value)}
        className="rounded border border-slate-300 px-1.5 py-0.5"
      >
        <option value="">move to…</option>
        {TARGETS.filter((t) => t !== device.state).map((t) => (
          <option key={t} value={t}>
            {t}
          </option>
        ))}
      </select>
      <button
        type="button"
        onClick={go}
        disabled={busy || !target}
        className="rounded bg-slate-700 px-2 py-0.5 font-medium text-white hover:bg-slate-800 disabled:opacity-50"
      >
        Apply
      </button>
      {message && (
        <span className={message.ok ? "text-emerald-700" : "text-red-700"}>{message.text}</span>
      )}
    </div>
  );
}