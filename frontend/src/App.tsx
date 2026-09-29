import { AppLayout } from "./components/AppLayout";
import { DashboardPage } from "./pages/DashboardPage";
import { DevicesSection } from "./components/devices/DevicesSection";
import { LocationConfigWizard } from "./components/config/LocationConfigWizard";

function App() {
  return (
    <AppLayout>
      <DashboardPage />
      <section id="devices">
        <DevicesSection />
      </section>
      <section id="configuration">
        <LocationConfigWizard />
      </section>
    </AppLayout>

  );
}

export default App;