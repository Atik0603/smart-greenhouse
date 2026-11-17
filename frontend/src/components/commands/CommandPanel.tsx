import { useEffect, useState } from "react";
import {
  listCommands,
  listDevices,
  submitCommand,
  type CommandLogDto,
  type CommandStatus,
  type DeviceDto,
} from "../../services/api";
import { ActuatorStateBadge } from "../devices/ActuatorStateBadge";

// Which controls EXIST for each device type. Whether they are ENABLED comes from allowed_commands.
const CONTROLS: Record<string, string[]> = {
  water_pump: ["start_pump", "stop_pump"],
  grow_light: ["set_light_level"],
};

const LABELS: Record<string, string> = {
  start_pump: "Start pump",
  stop_pump: "Stop pump",
  set_light_level: "Set level",
};

const STATUS_STYLES: Record<CommandStatus, string> = {
  success: "border-emerald-300 bg-emerald-100 text-emerald-800",
  failed: "border-red-300 bg-red-100 text-red-800",
  rejected: "border-amber-300 bg-amber-100 text-amber-800",
};

const DEFAULT_LEVEL = 1;

function StatusBadge({ status }: { status: CommandStatus }) {
  return (
    <span className={`rounded-full border px-2 py-0.5 text-xs font-semibold uppercase ${STATUS_STYLES[status]}`}>
      {status}
    </span>
  );
}

export default function CommandPanel() {
  const [actuators, setActuators] = useState<DeviceDto[]>([]);
  const [history, setHistory] = useState<CommandLogDto[]>([]);
  const [levels, setLevels] = useState<Record<string, number>>({});
  const [busyDevice, setBusyDevice] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<CommandLogDto | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function reload() {
    try {
      const [devices, rows] = await Promise.all([listDevices({ role: "actuator" }), listCommands(20)]);
      setActuators(devices);
      setHistory(rows);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  useEffect(() => {
    reload();
  }, []);

  async function send(device: DeviceDto, commandType: string) {
    setBusyDevice(device.id);
    setError(null);
    setLastResult(null);
    try {
      const payload =
        commandType === "set_light_level" ? { level: levels[device.id] ?? DEFAULT_LEVEL } : {};
      setLastResult(await submitCommand(device.id, commandType, payload));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyDevice(null);
      await reload(); // fresh state + allowed_commands + history after every click
    }
  }

  return (
    <div className="space-y-4">
      {/* --- Controls --- */}
      <div className="space-y-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-slate-800">Actuator controls</h2>
          <button
            type="button"
            onClick={reload}
            className="rounded bg-slate-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800"
          >
            Refresh
          </button>
        </div>

        <p className="text-xs text-slate-500">
          Buttons are enabled only for commands the actuator allows in its current state. Every
          click is recorded in the command history below, including rejected ones.
        </p>

        {lastResult && (
          <div className="flex flex-wrap items-center gap-2 rounded border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
            <StatusBadge status={lastResult.status} />
            <span className="font-medium text-slate-700">{lastResult.command_type}</span>
            {lastResult.error_message && <span className="text-slate-600">{lastResult.error_message}</span>}
          </div>
        )}

        {error && (
          <p className="rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>
        )}

        {actuators.length === 0 ? (
          <p className="text-sm italic text-slate-400">No actuators yet. Provision a kit in the Devices section.</p>
        ) : (
          <ul className="divide-y divide-slate-100 rounded border border-slate-200">
            {actuators.map((d) => (
              <li key={d.id} className="flex flex-wrap items-center gap-3 px-3 py-2 text-sm">
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium text-slate-800">{d.display_name || "(unnamed)"}</p>
                  <p className="text-xs text-slate-400">{d.device_type}</p>
                </div>
                <ActuatorStateBadge device={d} />

                {(CONTROLS[d.device_type] ?? []).map((cmd) => {
                  const allowed = d.allowed_commands.includes(cmd);
                  return (
                    <div key={cmd} className="flex items-center gap-1">
                      {cmd === "set_light_level" && (
                        <input
                          type="number"
                          min={0}
                          max={100}
                          value={levels[d.id] ?? DEFAULT_LEVEL}
                          onChange={(e) => setLevels((prev) => ({ ...prev, [d.id]: Number(e.target.value) }))}
                          className="w-16 rounded border border-slate-300 px-1.5 py-0.5"
                          aria-label="Light level"
                        />
                      )}
                      <button
                        type="button"
                        onClick={() => send(d, cmd)}
                        disabled={!allowed || busyDevice === d.id}
                        title={allowed ? undefined : `Not allowed while ${d.state}`}
                        className="rounded bg-sky-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        {LABELS[cmd] ?? cmd}
                      </button>
                    </div>
                  );
                })}
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* --- History --- */}
      <div className="space-y-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-800">Command history</h2>
        {history.length === 0 ? (
          <p className="text-sm italic text-slate-400">No commands yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
                <tr>
                  <th className="py-2 pr-3">Time</th>
                  <th className="py-2 pr-3">Command</th>
                  <th className="py-2 pr-3">Device</th>
                  <th className="py-2 pr-3">Status</th>
                  <th className="py-2 pr-3">Payload</th>
                  <th className="py-2">Message</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {history.map((row) => (
                  <tr key={row.id}>
                    <td className="whitespace-nowrap py-2 pr-3 text-slate-600">
                      {new Date(row.created_at).toLocaleString()}
                    </td>
                    <td className="py-2 pr-3 font-medium text-slate-800">{row.command_type}</td>
                    <td className="py-2 pr-3 font-mono text-xs text-slate-500" title={row.device_id}>
                      {row.device_id.slice(0, 8)}
                    </td>
                    <td className="py-2 pr-3">
                      <StatusBadge status={row.status} />
                    </td>
                    <td className="py-2 pr-3 font-mono text-xs text-slate-500">
                      {Object.keys(row.payload).length ? JSON.stringify(row.payload) : "—"}
                    </td>
                    <td className="py-2 text-slate-600">{row.error_message ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}