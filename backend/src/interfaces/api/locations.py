from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.application.locations.config_service import LocationConfigService
from src.application.locations.dto import (
    LocationConfigCreateRequest,
    LocationConfigResponse,
    LocationSummaryDto,
)
from src.application.locations.mappers import (
    location_config_to_dto,
    location_summary_to_dto,
)
from src.domain.locations.errors import ConfigurationError, LocationNotFoundError, ZoneNotFoundError
from src.infrastructure.db import get_db
from src.infrastructure.persistence.location_repository import LocationRepository

from src.application.devices.dto import DeviceDto
from src.application.devices.mappers import devices_to_dtos
from src.application.locations.zone_assignment_service import ZoneAssignmentService
from src.interfaces.api.devices import get_zone_assignment_service

router = APIRouter(prefix="/api/locations", tags=["locations"])


def get_config_service(db: Session = Depends(get_db)) -> LocationConfigService:
    return LocationConfigService(LocationRepository(db))


@router.get(
    "",
    response_model=list[LocationSummaryDto],
    summary="List saved locations (newest first)",
)
def list_locations(
    service: LocationConfigService = Depends(get_config_service),
) -> list[LocationSummaryDto]:
    return [location_summary_to_dto(s) for s in service.list_locations()]


@router.post(
    "/config",
    response_model=LocationConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a location with one or more zones (validated by the builder)",
)
def create_location_config(
    request: LocationConfigCreateRequest,
    service: LocationConfigService = Depends(get_config_service),
) -> LocationConfigResponse:
    try:
        location = service.create_config(request)
    except ConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return location_config_to_dto(location)


@router.get(
    "/{location_id}/config",
    response_model=LocationConfigResponse,
    summary="Get a saved location with its zones",
)
def get_location_config(
    location_id: UUID,
    service: LocationConfigService = Depends(get_config_service),
) -> LocationConfigResponse:
    try:
        location = service.get_config(location_id)
    except LocationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return location_config_to_dto(location)


@router.delete(
    "/{location_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a location and its zones; its devices become unassigned",
)
def delete_location(
    location_id: UUID,
    service: LocationConfigService = Depends(get_config_service),
) -> None:
    try:
        service.delete_location(location_id)
    except LocationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/{location_id}/zones/{zone_id}/devices",
    response_model=list[DeviceDto],
    summary="List sensors and actuators assigned to a zone of this location",
)
def list_zone_devices(
    location_id: UUID,
    zone_id: UUID,
    service: ZoneAssignmentService = Depends(get_zone_assignment_service),
) -> list[DeviceDto]:
    try:
        devices = service.list_zone_devices(location_id, zone_id)
    except ZoneNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return devices_to_dtos(devices)