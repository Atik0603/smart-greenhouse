import { SensorList } from "../features/sensors/SensorList";
import OverviewPanel from "../features/overview/OverviewPanel";

export function DashboardPage() {
  return (
    <div className="space-y-4">
      <section id="overview">
        <OverviewPanel />
      </section>
      <section id="sensors" className="rounded-lg border bg-white p-4">
        <h2 className="font-medium text-gray-700 mb-2">Sensors</h2>
        <SensorList />
      </section>
    </div>
  );
}