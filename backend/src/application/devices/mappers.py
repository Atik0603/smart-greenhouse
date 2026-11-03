from src.application.devices.dto import DeviceDto
from src.domain.devices.entity import Device
from src.application.devices.actuator_state_service import ActuatorStateView
from uuid import UUID


def device_to_dto(device: Device) -> DeviceDto:
    if device.id is None:
        raise ValueError("Cannot map an unsaved device (id is None) to a DTO")
    return DeviceDto(
        id=device.id,
        device_type=device.device_type,
        role=device.role,
        device_family=device.device_family,
        display_name=device.display_name,
        default_config=device.default_config,
        zone_id=device.zone_id,
        location_id=device.location_id,
        sampling_interval_seconds=device.sampling_interval_seconds,
        tracking_enabled=device.tracking_enabled,
    )


def devices_to_dtos(devices: list[Device]) -> list[DeviceDto]:
    
    return [device_to_dto(d) for d in devices]


def with_state(
    dtos: list[DeviceDto], views: dict[UUID, ActuatorStateView]
) -> list[DeviceDto]:
    """Copy state + allowed_commands onto the DTOs of actuators. Sensors are left as they are."""
    for dto in dtos:
        view = views.get(dto.id)
        if view is not None:
            dto.state = view.state
            dto.allowed_commands = view.allowed_commands
    return dtos