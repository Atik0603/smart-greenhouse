import { AppLayout } from "./components/AppLayout";
import { DashboardPage } from "./pages/DashboardPage";
import { DevicesSection } from "./components/devices/DevicesSection";

function App() {
  return (
    <AppLayout>
      <DashboardPage />
      <section id="devices">
        <DevicesSection />
      </section>
    </AppLayout>

  );
}

export default App;