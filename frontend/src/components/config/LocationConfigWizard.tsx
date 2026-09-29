import { useCallback, useEffect, useState } from "react";
import {
  addZone,
  deleteLocation,
  getLocationConfig,
  listLocations,
  listZoneDevices,
  type DeviceDto,
  type LocationConfigResponse,
  type LocationSummaryDto,
} from "../../services/api";
import {
  draftToZoneInput,
  emptyZoneDraft,
  errorMessage,
  validateZoneDraft,
  type ZoneDraft,
} from "./configHelpers";
import { LocationCreateForm } from "./LocationCreateForm";
import { ZoneEditor } from "./ZoneEditor";
import { ZoneFields } from "./ZoneFields";

interface Props {
  onConfigChanged?: () => void; // tell the rest of the dashboard that locations/zones changed
  refreshKey?: number;          // bumped by others (e.g. a device was assigned) to reload zone device lists
}

export function LocationConfigWizard({ onConfigChanged, refreshKey = 0 }: Props) {
  const [locations, setLocations] = useState<LocationSummaryDto[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [config, setConfig] = useState<LocationConfigResponse | null>(null);
  const [zoneDevices, setZoneDevices] = useState<Record<string, DeviceDto[]>>({});
  const [configLoading, setConfigLoading] = useState(false);
  const [configError, setConfigError] = useState<string | null>(null);
  const [configVersion, setConfigVersion] = useState(0);

  const [newZone, setNewZone] = useState<ZoneDraft>(emptyZoneDraft());
  const [addZoneError, setAddZoneError] = useState<string | null>(null);
  const [addingZone, setAddingZone] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  // --- Load the location list once on page load ---
  useEffect(() => {
    listLocations()
      .then(setLocations)
      .catch((e: unknown) => setListError(errorMessage(e)))
      .finally(() => setListLoading(false));
  }, []);

  // --- Load the selected location's config + each zone's devices ---
  useEffect(() => {
    if (!selectedId) {
      setConfig(null);
      setZoneDevices({});
      return;
    }
    let ignore = false;
    setConfigLoading(true);
    setConfigError(null);

    (async () => {
      try {
        const cfg = await getLocationConfig(selectedId);
        if (ignore) return;
        setConfig(cfg);
        const lists = await Promise.all(cfg.zones.map((z) => listZoneDevices(selectedId, z.id)));
        if (ignore) return;
        setZoneDevices(Object.fromEntries(cfg.zones.map((z, i) => [z.id, lists[i]])));
      } catch (e) {
        if (!ignore) setConfigError(errorMessage(e));
      } finally {
        if (!ignore) setConfigLoading(false);
      }
    })();

    return () => {
      ignore = true;
    };
  }, [selectedId, configVersion, refreshKey]);

  const reloadSelected = useCallback(() => {
    setConfigVersion((v) => v + 1);
    onConfigChanged?.();
  }, [onConfigChanged]);

  function handleCreated(created: LocationConfigResponse) {
    setLocations((prev) => [created.location, ...prev.filter((l) => l.id !== created.location.id)]);
    setSelectedId(created.location.id);
    setNotice(`Created "${created.location.name}" with ${created.zones.length} zone(s).`);
    onConfigChanged?.();
  }

  async function handleDeleteLocation(loc: LocationSummaryDto) {
    if (!window.confirm(`Delete location "${loc.name}" and all its zones? Devices in it become unassigned.`)) return;
    setNotice(null);
    try {
      await deleteLocation(loc.id);
      setLocations((prev) => prev.filter((l) => l.id !== loc.id));
      if (selectedId === loc.id) setSelectedId(null);
      setNotice(`Deleted "${loc.name}".`);
      onConfigChanged?.();
    } catch (e) {
      setListError(errorMessage(e));
    }
  }

  async function handleAddZone() {
    if (!config) return;
    const problem =
      validateZoneDraft(newZone) ??
      (config.zones.some((z) => z.name.toLowerCase() === newZone.name.trim().toLowerCase())
        ? `Zone name "${newZone.name.trim()}" already exists in this location`
        : null);
    if (problem) {
      setAddZoneError(problem);
      return;
    }
    setAddingZone(true);
    setAddZoneError(null);
    try {
      await addZone(config.location.id, draftToZoneInput(newZone));
      setNewZone(emptyZoneDraft());
      reloadSelected();
    } catch (e) {
      setAddZoneError(errorMessage(e));
    } finally {
      setAddingZone(false);
    }
  }

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-slate-900">Configuration</h2>
      {notice && <p className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{notice}</p>}

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Left: saved locations + create form */}
        <div className="space-y-4">
          <div className="rounded-lg border border-slate-200 bg-white">
            <h3 className="border-b border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700">
              Saved locations
            </h3>
            {listLoading ? (
              <p className="px-4 py-3 text-sm text-slate-500">Loading locations…</p>
            ) : listError ? (
              <p className="px-4 py-3 text-sm text-red-600">{listError}</p>
            ) : locations.length === 0 ? (
              <p className="px-4 py-3 text-sm text-slate-500">No locations yet. Create one below.</p>
            ) : (
              <ul className="divide-y divide-slate-200">
                {locations.map((loc) => (
                  <li key={loc.id} className={`flex items-center justify-between gap-2 px-4 py-2 ${loc.id === selectedId ? "bg-emerald-50" : ""}`}>
                    <button type="button" onClick={() => setSelectedId(loc.id)} className="min-w-0 truncate text-left text-sm font-medium text-slate-900 hover:text-emerald-700">
                      {loc.name}
                    </button>
                    <button type="button" onClick={() => handleDeleteLocation(loc)} className="shrink-0 text-xs text-slate-500 hover:text-red-600">
                      Delete
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <LocationCreateForm onCreated={handleCreated} />
        </div>

        {/* Right: the selected location */}
        <div className="space-y-4">
          {!selectedId ? (
            <p className="rounded-lg border border-dashed border-slate-300 px-4 py-6 text-center text-sm text-slate-500">
              Select a location to see and manage its zones.
            </p>
          ) : configError ? (
            <p className="text-sm text-red-600">Could not load location: {configError}</p>
          ) : !config ? (
            <p className="text-sm text-slate-500">Loading location…</p>
          ) : (
            <>
              <div>
                <h3 className="font-semibold text-slate-900">{config.location.name}</h3>
                <p className="break-all text-xs text-slate-500">location_id: {config.location.id}</p>
                {configLoading && <p className="text-xs text-slate-400">Refreshing…</p>}
              </div>

              <ul className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
                {config.zones.map((zone) => (
                  <ZoneEditor
                    key={zone.id}
                    locationId={config.location.id}
                    zone={zone}
                    devices={zoneDevices[zone.id]}
                    otherZoneNames={config.zones.filter((z) => z.id !== zone.id).map((z) => z.name)}
                    onChanged={reloadSelected}
                  />
                ))}
              </ul>

              <div className="space-y-3 rounded-lg border border-slate-200 bg-white p-4">
                <h4 className="text-sm font-semibold text-slate-700">Add a zone to {config.location.name}</h4>
                <ZoneFields draft={newZone} onChange={setNewZone} disabled={addingZone} />
                {addZoneError && <p className="text-xs text-red-600">{addZoneError}</p>}
                <button type="button" onClick={handleAddZone} disabled={addingZone} className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50">
                  {addingZone ? "Adding…" : "Add zone"}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}