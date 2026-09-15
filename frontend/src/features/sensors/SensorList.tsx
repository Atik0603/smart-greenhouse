import { useEffect, useState } from "react";
import { createSensor, listSensors, type SensorDto } from "../../services/api";

export function SensorList() {
  const [sensors, setSensors] = useState<SensorDto[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      setSensors(await listSensors());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load sensors");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleAdd(type: "moisture" | "light") {
    setAdding(true);
    setError(null);
    try {
      await createSensor(type);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add sensor");
    } finally {
      setAdding(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <button
          onClick={() => handleAdd("moisture")}
          disabled={adding}
          className="px-3 py-1.5 rounded bg-emerald-600 text-white text-sm disabled:opacity-50"
        >
          Add moisture sensor
        </button>
        <button
          onClick={() => handleAdd("light")}
          disabled={adding}
          className="px-3 py-1.5 rounded bg-amber-600 text-white text-sm disabled:opacity-50"
        >
          Add light sensor
        </button>
      </div>

      {error && <p className="text-red-600 text-sm">{error}</p>}

      {loading ? (
        <p className="text-sm text-gray-500">Loading sensors…</p>
      ) : sensors.length === 0 ? (
        <p className="text-sm text-gray-500">No sensors yet.</p>
      ) : (
        <ul className="divide-y divide-gray-200">
          {sensors.map((s) => (
            <li key={s.id} className="py-2 text-sm">
              <span className="font-medium">{s.display_name}</span>{" "}
              <span className="text-gray-500">({s.device_type})</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}