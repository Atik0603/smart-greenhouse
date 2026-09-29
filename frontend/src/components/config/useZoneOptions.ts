import { useEffect, useState } from "react";
import { getLocationConfig, listLocations } from "../../services/api";
import { errorMessage } from "./configHelpers";

export interface ZoneOption {
  zoneId: string;
  zoneName: string;
  locationId: string;
  locationName: string;
}

export interface ZoneGroup {
  locationId: string;
  locationName: string;
  zones: ZoneOption[];
}

export const zoneLabel = (z: ZoneOption): string => `${z.locationName} — ${z.zoneName}`;

export function useZoneOptions(refreshKey: number) {
  const [groups, setGroups] = useState<ZoneGroup[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    (async () => {
      try {
        const locations = await listLocations();
        const configs = await Promise.all(locations.map((l) => getLocationConfig(l.id)));
        if (ignore) return;
        setGroups(
          configs.map((cfg) => ({
            locationId: cfg.location.id,
            locationName: cfg.location.name,
            zones: cfg.zones.map((z) => ({
              zoneId: z.id,
              zoneName: z.name,
              locationId: cfg.location.id,
              locationName: cfg.location.name,
            })),
          })),
        );
        setError(null);
      } catch (e) {
        if (!ignore) setError(errorMessage(e));
      }
    })();
    return () => {
      ignore = true;
    };
  }, [refreshKey]);

  return { groups, error };
}