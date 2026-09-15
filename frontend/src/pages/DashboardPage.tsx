import { SensorList } from "../features/sensors/SensorList";

export function DashboardPage() {
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      <section className="rounded-lg border bg-white p-4">
        <h2 className="font-medium text-gray-700">Devices</h2>
        <p className="text-sm text-gray-400">Coming in a later phase.</p>
      </section>
      <section id="sensors" className="rounded-lg border bg-white p-4">
        <h2 className="font-medium text-gray-700 mb-2">Sensors</h2>
        <SensorList />
      </section>
      <section className="rounded-lg border bg-white p-4">
        <h2 className="font-medium text-gray-700">Sensor Readings</h2>
        <p className="text-sm text-gray-400">Coming in a later phase.</p>
      </section>
    </div>
  );
}