export interface HealthResponse {
  status: string;
  db: "ok" | "fail";
}

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export async function getHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error("Health check failed");
  return res.json();
}

export type SensorDto = {
  id: string;
  device_type: string;
  display_name: string;
  default_config: Record<string, unknown>;
};


export async function listSensors(): Promise<SensorDto[]> {
  const res = await fetch(`${API_BASE}/api/sensors`);
  if (!res.ok) throw new Error(`Failed to list sensors: ${res.status}`);
  return res.json();
}

export async function createSensor(
  type: "moisture" | "light",
  displayName?: string
): Promise<SensorDto> {
  const res = await fetch(`${API_BASE}/api/sensors`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type, display_name: displayName ?? null }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Failed to create sensor: ${res.status}`);
  }
  return res.json();
}


// --- Phase 3: devices ---

export type DeviceRole = "sensor" | "actuator";
export type DeviceFamily = "simulation" | "edge";

export interface DeviceDto {
  id: string;
  device_type: string;
  role: DeviceRole;
  device_family: string;
  display_name: string;
  default_config: Record<string, unknown>;
}

export async function listDevices(
  filters: { family?: string; role?: DeviceRole } = {},
): Promise<DeviceDto[]> {
  const params = new URLSearchParams();
  if (filters.family) params.set("family", filters.family);
  if (filters.role) params.set("role", filters.role);
  const query = params.toString();

  const res = await fetch(`${API_BASE}/api/devices${query ? `?${query}` : ""}`);
  if (!res.ok) throw new Error(`Failed to load devices (${res.status})`);
  return res.json();
}

export async function provisionFamily(family: DeviceFamily): Promise<DeviceDto[]> {
  const res = await fetch(
    `${API_BASE}/api/devices/provision?family=${encodeURIComponent(family)}`,
    { method: "POST" },
  );
  if (!res.ok) throw new Error(`Failed to provision ${family} kit (${res.status})`);
  return res.json();
}