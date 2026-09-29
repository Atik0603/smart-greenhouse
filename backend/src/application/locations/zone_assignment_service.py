from uuid import UUID

from src.domain.devices.entity import Device
from src.domain.devices.errors import DeviceNotFoundError
from src.domain.locations.errors import ZoneNotFoundError
from src.infrastructure.persistence.device_repository import DeviceRepository
from src.infrastructure.persistence.location_repository import LocationRepository


class ZoneAssignmentService:
    def __init__(
        self, device_repository: DeviceRepository, location_repository: LocationRepository
    ) -> None:
        self.devices = device_repository
        self.locations = location_repository

    def assign(self, device_id: UUID, zone_id: UUID | None) -> Device:
        if zone_id is None:
            device = self.devices.set_zone_assignment(device_id, None, None)
        else:
            found = self.locations.get_zone(zone_id)
            if found is None:
                raise ZoneNotFoundError(zone_id)
            _zone, location_id = found
            device = self.devices.set_zone_assignment(device_id, zone_id, location_id)

        if device is None:
            raise DeviceNotFoundError(device_id)
        return device

    def list_zone_devices(self, location_id: UUID, zone_id: UUID) -> list[Device]:
        found = self.locations.get_zone(zone_id)
        if found is None or found[1] != location_id:
            raise ZoneNotFoundError(zone_id)
        return self.devices.list_devices_in_zone(zone_id)