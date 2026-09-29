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
  zone_id: string | null;
  location_id: string | null;
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

// --- Phase 4: locations and zones ---

export interface LocationSummaryDto {
  id: string;
  name: string;
}

export interface ZoneReadDto {
  id: string;
  location_id: string;
  name: string;
  moisture_threshold_low: number;
  moisture_threshold_high: number;
  schedule: Record<string, unknown>;
}

export interface LocationConfigResponse {
  location: LocationSummaryDto;
  zones: ZoneReadDto[];
}

export interface ZoneInput {
  name: string;
  moisture_threshold_low: number;
  moisture_threshold_high: number;
  schedule?: Record<string, unknown>;
}

export interface LocationConfigCreateRequest {
  location_name: string;
  zones: ZoneInput[];
}

export type ZoneUpdateRequest = Partial<ZoneInput>;

const JSON_HEADERS = { "Content-Type": "application/json" };

async function errorFrom(res: Response, fallback: string): Promise<Error> {
  const body = await res.json().catch(() => ({}));
  const detail = typeof body.detail === "string" ? body.detail : fallback;
  return new Error(detail);
}

export async function listLocations(): Promise<LocationSummaryDto[]> {
  const res = await fetch(`${API_BASE}/api/locations`);
  if (!res.ok) throw await errorFrom(res, `Failed to load locations (${res.status})`);
  return res.json();
}

export async function getLocationConfig(locationId: string): Promise<LocationConfigResponse> {
  const res = await fetch(`${API_BASE}/api/locations/${locationId}/config`);
  if (!res.ok) throw await errorFrom(res, `Failed to load location (${res.status})`);
  return res.json();
}

export async function createLocationConfig(
  request: LocationConfigCreateRequest,
): Promise<LocationConfigResponse> {
  const res = await fetch(`${API_BASE}/api/locations/config`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify(request),
  });
  if (!res.ok) throw await errorFrom(res, `Failed to create location (${res.status})`);
  return res.json();
}

export async function deleteLocation(locationId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/locations/${locationId}`, { method: "DELETE" });
  if (!res.ok) throw await errorFrom(res, `Failed to delete location (${res.status})`);
}

export async function addZone(locationId: string, zone: ZoneInput): Promise<ZoneReadDto> {
  const res = await fetch(`${API_BASE}/api/locations/${locationId}/zones`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify(zone),
  });
  if (!res.ok) throw await errorFrom(res, `Failed to add zone (${res.status})`);
  return res.json();
}

export async function updateZone(
  locationId: string,
  zoneId: string,
  changes: ZoneUpdateRequest,
): Promise<ZoneReadDto> {
  const res = await fetch(`${API_BASE}/api/locations/${locationId}/zones/${zoneId}`, {
    method: "PATCH",
    headers: JSON_HEADERS,
    body: JSON.stringify(changes),
  });
  if (!res.ok) throw await errorFrom(res, `Failed to update zone (${res.status})`);
  return res.json();
}

export async function deleteZone(locationId: string, zoneId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/locations/${locationId}/zones/${zoneId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw await errorFrom(res, `Failed to delete zone (${res.status})`);
}

export async function listZoneDevices(locationId: string, zoneId: string): Promise<DeviceDto[]> {
  const res = await fetch(`${API_BASE}/api/locations/${locationId}/zones/${zoneId}/devices`);
  if (!res.ok) throw await errorFrom(res, `Failed to load zone devices (${res.status})`);
  return res.json();
}

export async function assignDeviceZone(deviceId: string, zoneId: string | null): Promise<DeviceDto> {
  const res = await fetch(`${API_BASE}/api/devices/${deviceId}/zone`, {
    method: "PATCH",
    headers: JSON_HEADERS,
    body: JSON.stringify({ zone_id: zoneId }),
  });
  if (!res.ok) throw await errorFrom(res, `Failed to assign zone (${res.status})`);
  return res.json();
}