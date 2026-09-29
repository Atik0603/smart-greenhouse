import { useEffect, useState } from "react";
import {
  listDevices,
  provisionFamily,
  type DeviceDto,
  type DeviceFamily,
} from "../../services/api";
import { DeviceFamilySwitcher } from "./DeviceFamilySwitcher";
import { DeviceList } from "./DeviceList";

export function DevicesSection() {
  const [family, setFamily] = useState<DeviceFamily>("simulation");
  const [devices, setDevices] = useState<DeviceDto[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [provisioning, setProvisioning] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let ignore = false;
    setLoading(true);
    setError(null);

    listDevices({ family })
      .then((data) => {
        if (!ignore) setDevices(data);
      })
      .catch((e: unknown) => {
        if (!ignore) setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!ignore) setLoading(false);
      });

    return () => {
      ignore = true;
    };
  }, [family, reloadKey]);

  async function handleProvision() {
    setProvisioning(true);
    setError(null);
    try {
      await provisionFamily(family);
      setReloadKey((k) => k + 1);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setProvisioning(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-slate-900">Devices</h2>
        <div className="flex flex-wrap items-center gap-3">
          <DeviceFamilySwitcher value={family} onChange={setFamily} disabled={provisioning} />
          <button
            type="button"
            onClick={handleProvision}
            disabled={provisioning}
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
          >
            {provisioning ? "Provisioning…" : `Provision ${family} kit`}
          </button>
        </div>
      </div>
      <DeviceList devices={devices} loading={loading} error={error} />
    </div>
  );
}