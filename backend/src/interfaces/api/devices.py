from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.application.devices.dto import DeviceDto
from src.application.devices.family_service import DeviceFamilyService
from src.application.devices.mappers import device_to_dto, devices_to_dtos
from src.domain.devices.family_factory import UnknownDeviceFamilyError
from src.infrastructure.db import get_db
from src.infrastructure.persistence.device_repository import DeviceRepository

from uuid import UUID

from src.application.locations.dto import DeviceZoneAssignmentRequest
from src.application.locations.zone_assignment_service import ZoneAssignmentService
from src.domain.devices.errors import DeviceNotFoundError
from src.domain.locations.errors import ZoneNotFoundError
from src.infrastructure.persistence.location_repository import LocationRepository

router = APIRouter(prefix="/api/devices", tags=["devices"])


def get_device_service(db: Session = Depends(get_db)) -> DeviceFamilyService:
    return DeviceFamilyService(DeviceRepository(db))


@router.get("", response_model=list[DeviceDto])
def list_devices(
    family: str | None = Query(default=None, description="Filter by family, e.g. simulation or edge"),
    role: Literal["sensor", "actuator"] | None = Query(default=None, description="Filter by role"),
    service: DeviceFamilyService = Depends(get_device_service),
) -> list[DeviceDto]:
    return devices_to_dtos(service.list_devices(family=family, role=role))


@router.post(
    "/provision",
    response_model=list[DeviceDto],
    status_code=status.HTTP_201_CREATED,
    summary="Provision a matching device kit (2 sensors + 2 actuators) for one family",
)
def provision_family(
    family: str = Query(..., description="Device family to provision: simulation or edge"),
    service: DeviceFamilyService = Depends(get_device_service),
) -> list[DeviceDto]:
    try:
        devices = service.provision_family(family)
    except UnknownDeviceFamilyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return devices_to_dtos(devices)

def get_zone_assignment_service(db: Session = Depends(get_db)) -> ZoneAssignmentService:
    return ZoneAssignmentService(DeviceRepository(db), LocationRepository(db))


@router.patch(
    "/{device_id}/zone",
    response_model=DeviceDto,
    summary="Assign a device to a zone (location is copied from the zone), or unassign with null",
)
def assign_device_zone(
    device_id: UUID,
    request: DeviceZoneAssignmentRequest,
    service: ZoneAssignmentService = Depends(get_zone_assignment_service),
) -> DeviceDto:
    try:
        device = service.assign(device_id, request.zone_id)
    except (DeviceNotFoundError, ZoneNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return device_to_dto(device)