from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.application.devices.actuator_state_service import ActuatorStateService
from src.application.devices.dto import (
    ActuatorStateDto,
    DeviceDto,
    SamplingUpdateRequest,
    TransitionRequest,
)
from src.application.devices.family_service import DeviceFamilyService
from src.application.devices.mappers import device_to_dto, devices_to_dtos, with_state
from src.application.devices.sampling_service import SamplingService
from src.application.locations.dto import DeviceZoneAssignmentRequest
from src.application.locations.zone_assignment_service import ZoneAssignmentService
from src.domain.actuators.errors import (
    IllegalTransitionError,
    NotAnActuatorError,
    UnknownStateError,
)
from src.domain.devices.errors import DeviceNotFoundError
from src.domain.devices.family_factory import UnknownDeviceFamilyError
from src.domain.devices.sampling import SamplingConfigError
from src.domain.locations.errors import ZoneNotFoundError
from src.infrastructure.db import get_db
from src.infrastructure.persistence.actuator_state_repository import ActuatorStateRepository
from src.infrastructure.persistence.device_repository import DeviceRepository
from src.infrastructure.persistence.location_repository import LocationRepository

router = APIRouter(prefix="/api/devices", tags=["devices"])


def get_device_service(db: Session = Depends(get_db)) -> DeviceFamilyService:
    return DeviceFamilyService(DeviceRepository(db))


def get_actuator_state_service(db: Session = Depends(get_db)) -> ActuatorStateService:
    return ActuatorStateService(DeviceRepository(db), ActuatorStateRepository(db))


@router.get("", response_model=list[DeviceDto])
def list_devices(
    family: str | None = Query(default=None, description="Filter by family, e.g. simulation or edge"),
    role: Literal["sensor", "actuator"] | None = Query(default=None, description="Filter by role"),
    service: DeviceFamilyService = Depends(get_device_service),
    states: ActuatorStateService = Depends(get_actuator_state_service),
) -> list[DeviceDto]:
    devices = service.list_devices(family=family, role=role)
    return with_state(devices_to_dtos(devices), states.views_for(devices))


@router.post(
    "/provision",
    response_model=list[DeviceDto],
    status_code=status.HTTP_201_CREATED,
    summary="Provision a matching device kit (2 sensors + 2 actuators) for one family",
)
def provision_family(
    family: str = Query(..., description="Device family to provision: simulation or edge"),
    service: DeviceFamilyService = Depends(get_device_service),
    states: ActuatorStateService = Depends(get_actuator_state_service),
) -> list[DeviceDto]:
    try:
        devices = service.provision_family(family)
    except UnknownDeviceFamilyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return with_state(devices_to_dtos(devices), states.views_for(devices))


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
    states: ActuatorStateService = Depends(get_actuator_state_service),
) -> DeviceDto:
    try:
        device = service.assign(device_id, request.zone_id)
    except (DeviceNotFoundError, ZoneNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return with_state([device_to_dto(device)], states.views_for([device]))[0]


def get_sampling_service(db: Session = Depends(get_db)) -> SamplingService:
    return SamplingService(DeviceRepository(db))


@router.patch(
    "/{device_id}/sampling",
    response_model=DeviceDto,
    summary="Set a sensor's sampling interval (min 5 s) and turn background tracking on/off",
)
def update_sampling(
    device_id: UUID,
    request: SamplingUpdateRequest,
    service: SamplingService = Depends(get_sampling_service),
) -> DeviceDto:
    try:
        device = service.update(device_id, request.sampling_interval_seconds, request.tracking_enabled)
    except DeviceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except SamplingConfigError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return device_to_dto(device)


@router.post(
    "/{device_id}/transition",
    response_model=ActuatorStateDto,
    responses={
        400: {"description": "Not an actuator, or unknown target state"},
        404: {"description": "Device not found"},
        409: {"description": "Transition not allowed from the current state"},
    },
    summary="Move an actuator to a new lifecycle state (illegal moves are rejected and not saved)",
)
def transition_actuator(
    device_id: UUID,
    request: TransitionRequest,
    service: ActuatorStateService = Depends(get_actuator_state_service),
) -> ActuatorStateDto:
    try:
        view = service.transition(device_id, request.target)
    except DeviceNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (NotAnActuatorError, UnknownStateError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except IllegalTransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return ActuatorStateDto(
        device_id=device_id, state=view.state, allowed_commands=view.allowed_commands
    )