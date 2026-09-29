from src.domain.devices.entity import Device
from src.domain.devices.family_factory import get_family_factory
from src.infrastructure.persistence.device_repository import DeviceRepository


class DeviceFamilyService:
    def __init__(self, repository: DeviceRepository) -> None:
        self.repository = repository

    def provision_family(self, family: str) -> list[Device]:
        factory = get_family_factory(family)          # 1. pick the kitchen (once)
        device_set = factory.create_device_set()      # 2. kitchen makes the whole meal
        return self.repository.save_devices(device_set)  # 3. save the whole kit together

    def list_devices(
        self, family: str | None = None, role: str | None = None
    ) -> list[Device]:
        return self.repository.list_devices(family=family, role=role)