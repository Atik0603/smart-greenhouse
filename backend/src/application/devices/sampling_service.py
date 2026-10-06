from uuid import UUID

from src.domain.devices.entity import Device
from src.domain.devices.errors import DeviceNotFoundError
from src.domain.devices.sampling import SamplingConfigError, validate_sampling_interval
from src.infrastructure.persistence.device_repository import DeviceRepository


class SamplingService:
    def __init__(self, devices: DeviceRepository) -> None:
        self._devices = devices

    def update(self, device_id: UUID, interval_seconds: int, tracking_enabled: bool) -> Device:
        device = self._devices.get_device(device_id)
        if device is None:
            raise DeviceNotFoundError(device_id)
        if device.role != "sensor":
            raise SamplingConfigError("Only sensors have sampling settings")
        validate_sampling_interval(interval_seconds)
        updated = self._devices.update_sampling(device_id, interval_seconds, tracking_enabled)
        assert updated is not None
        return updated