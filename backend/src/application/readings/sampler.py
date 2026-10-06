import logging
from datetime import datetime

from src.application.readings.service import ReadingIngest
from src.domain.sensors.ports import SensorReadError
from src.infrastructure.persistence.device_repository import DeviceRepository
from src.infrastructure.persistence.reading_repository import ReadingRepository

logger = logging.getLogger(__name__)


class SimulationSampler:
    def __init__(
        self,
        devices: DeviceRepository,
        readings: ReadingRepository,
        ingest: ReadingIngest,
    ) -> None:
        self._devices = devices
        self._readings = readings
        self._ingest = ingest

    def run_once(self, now: datetime) -> int:
        """Record a reading for every enabled simulation sensor whose interval has elapsed.
        Returns how many readings were recorded."""
        candidates = self._devices.list_sampling_candidates()  # protocol=simulation, tracking on
        last_seen = self._readings.latest_recorded_at_by_device([d.id for d in candidates])

        recorded = 0
        for device in candidates:
            last = last_seen.get(device.id)
            due = last is None or (now - last).total_seconds() >= device.sampling_interval_seconds
            if not due:
                continue
            try:
                self._ingest.record(device.id, at=now)
                recorded += 1
            except SensorReadError as exc:
                logger.warning("Sampler skipped device %s: %s", device.id, exc)
        return recorded