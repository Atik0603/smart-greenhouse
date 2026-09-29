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

from src.application.locations.dto import ZoneCreateRequest, ZoneReadDto, ZoneUpdateRequest
from src.application.locations.mappers import zone_to_dto
from src.application.locations.zone_service import ZoneService

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

def get_zone_service(db: Session = Depends(get_db)) -> ZoneService:
    return ZoneService(LocationRepository(db))


@router.post(
    "/{location_id}/zones",
    response_model=ZoneReadDto,
    status_code=status.HTTP_201_CREATED,
    summary="Add a zone to a saved location",
)
def add_zone(
    location_id: UUID,
    request: ZoneCreateRequest,
    service: ZoneService = Depends(get_zone_service),
) -> ZoneReadDto:
    try:
        zone = service.add_zone(location_id, request)
    except LocationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return zone_to_dto(zone, location_id)


@router.patch(
    "/{location_id}/zones/{zone_id}",
    response_model=ZoneReadDto,
    summary="Update a zone's name, thresholds and/or schedule",
)
def update_zone(
    location_id: UUID,
    zone_id: UUID,
    request: ZoneUpdateRequest,
    service: ZoneService = Depends(get_zone_service),
) -> ZoneReadDto:
    try:
        zone = service.update_zone(location_id, zone_id, request)
    except (LocationNotFoundError, ZoneNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return zone_to_dto(zone, location_id)


@router.delete(
    "/{location_id}/zones/{zone_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a zone (not the last one); its devices become unassigned",
)
def delete_zone(
    location_id: UUID,
    zone_id: UUID,
    service: ZoneService = Depends(get_zone_service),
) -> None:
    try:
        service.delete_zone(location_id, zone_id)
    except (LocationNotFoundError, ZoneNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc