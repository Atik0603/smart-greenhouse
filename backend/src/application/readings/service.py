from dataclasses import replace
from datetime import datetime
from typing import Callable
from uuid import UUID

from src.application.readings.dto import ReadingDto
from src.application.readings.mappers import reading_to_dto
from src.domain.devices.entity import Device
from src.domain.devices.errors import DeviceNotFoundError
from src.domain.sensors.ports import SensorPort, SensorReadError
from src.domain.sensors.reading import Reading
from src.infrastructure.persistence.device_repository import DeviceRepository
from src.infrastructure.persistence.reading_repository import ReadingRepository

AdapterSelector = Callable[[Device], SensorPort]

MAX_HISTORY_LIMIT = 500


class ReadingIngest:
    def __init__(
        self,
        devices: DeviceRepository,
        readings: ReadingRepository,
        select_adapter: AdapterSelector,
    ) -> None:
        self._devices = devices
        self._readings = readings
        self._select_adapter = select_adapter

    def record(
        self,
        device_id: UUID,
        reading: Reading | None = None,
        at: datetime | None = None,
    ) -> ReadingDto:
        """The ONLY writer of sensor_readings.

        - reading=None  -> one-shot read through the device's adapter (manual read, sampler)
        - reading given -> an already translated reading (e.g. MqttSensorAdapter.translate)
        - at            -> override recorded_at (the sampler's tick time)
        """
        device = self._load_sensor(device_id)

        if reading is None:
            reading = self._select_adapter(device).read(device)
        elif reading.device_id != device.id:
            raise SensorReadError("Reading belongs to a different device")

        if at is not None:
            reading = replace(reading, recorded_at=at)

        saved = self._readings.add(reading)
        return reading_to_dto(saved)

    def list_recent(self, device_id: UUID, limit: int = 20) -> list[ReadingDto]:
        self._load_sensor(device_id)
        limit = max(1, min(limit, MAX_HISTORY_LIMIT))
        return [reading_to_dto(r) for r in self._readings.list_recent(device_id, limit)]

    def _load_sensor(self, device_id: UUID) -> Device:
        device = self._devices.get_device(device_id)
        if device is None:
            raise DeviceNotFoundError(device_id)
        if device.role != "sensor":
            raise SensorReadError(f"Device {device_id} is a {device.role}, not a sensor")
        return device