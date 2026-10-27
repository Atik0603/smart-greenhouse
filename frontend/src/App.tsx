import { AppLayout } from "./components/AppLayout";
import { DashboardPage } from "./pages/DashboardPage";
import { DevicesSection } from "./components/devices/DevicesSection";
import { LocationConfigWizard } from "./components/config/LocationConfigWizard";
import { useState } from "react";
import StrategyPanel from "./features/automation/StrategyPanel";

function App() {
  const [configVersion, setConfigVersion] = useState(0);
  const [devicesVersion, setDevicesVersion] = useState(0);

  return (
    <AppLayout>
      <DashboardPage />
      <section id="devices">
        <DevicesSection
          configVersion={configVersion}
          onDevicesChanged={() => setDevicesVersion((v) => v + 1)}
        />
      </section>
      <section id="configuration">
        <LocationConfigWizard
          onConfigChanged={() => setConfigVersion((v) => v + 1)}
          refreshKey={devicesVersion}
        />
      </section>
      <section id="automation" className="space-y-3">
        <StrategyPanel />
      </section>
    </AppLayout>
  );
}

export default App;