import type { ZoneInput, ZoneReadDto } from "../../services/api";

// Form inputs hold strings: a number field can be half-typed or empty.
export interface ZoneDraft {
  name: string;
  low: string;
  high: string;
  waterAt: string;
}

export const emptyZoneDraft = (): ZoneDraft => ({ name: "", low: "0.2", high: "0.4", waterAt: "" });

export function validateZoneDraft(d: ZoneDraft): string | null {
  if (!d.name.trim()) return "Zone name is required";
  if (d.low.trim() === "" || d.high.trim() === "") return "Both thresholds are required";
  const low = Number(d.low);
  const high = Number(d.high);
  if (Number.isNaN(low) || Number.isNaN(high)) return "Thresholds must be numbers";
  if (low < 0 || low > 1 || high < 0 || high > 1) return "Thresholds must be between 0 and 1";
  if (low >= high) return "Low threshold must be less than high";
  return null;
}

export function findDuplicateZoneName(names: string[]): string | null {
  const seen = new Set<string>();
  for (const name of names) {
    const key = name.trim().toLowerCase();
    if (!key) continue;
    if (seen.has(key)) return `Zone name "${name.trim()}" is used more than once`;
    seen.add(key);
  }
  return null;
}

export function draftToZoneInput(d: ZoneDraft, baseSchedule: Record<string, unknown> = {}): ZoneInput {
  const schedule: Record<string, unknown> = { ...baseSchedule };
  if (d.waterAt) schedule.water_at = d.waterAt;
  else delete schedule.water_at;
  return {
    name: d.name.trim(),
    moisture_threshold_low: Number(d.low),
    moisture_threshold_high: Number(d.high),
    schedule,
  };
}

export function zoneToDraft(z: ZoneReadDto): ZoneDraft {
  return {
    name: z.name,
    low: String(z.moisture_threshold_low),
    high: String(z.moisture_threshold_high),
    waterAt: typeof z.schedule.water_at === "string" ? z.schedule.water_at : "",
  };
}

export const errorMessage = (e: unknown): string => (e instanceof Error ? e.message : String(e));