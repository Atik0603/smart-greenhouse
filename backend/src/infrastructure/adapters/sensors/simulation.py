import random
from typing import Callable
from datetime import datetime

from src.domain.devices.entity import Device
from src.domain.sensors.ports import SensorPort, SensorReadError
from src.domain.sensors.reading import Reading, utc_now

# device_type -> (min, max, unit). Documented ranges from the Phase 5 requirements.
SIMULATION_RANGES: dict[str, tuple[float, float, str]] = {
    "moisture_sensor": (0.2, 0.6, "vwc"),
    "light_sensor": (200.0, 2000.0, "lux"),
}


class SimulationSensorAdapter(SensorPort):
    def __init__(
        self,
        rng: random.Random | None = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._rng = rng or random.Random()
        self._clock = clock

    def read(self, device: Device) -> Reading:
        spec = SIMULATION_RANGES.get(device.device_type)
        if spec is None:
            raise SensorReadError(
                f"Simulation has no generator for device type '{device.device_type}'"
            )
        low, high, unit = spec
        return Reading(
            device_id=device.id,
            value=round(self._rng.uniform(low, high), 4),
            unit=unit,
            source="simulation",
            recorded_at=self._clock(),
        )