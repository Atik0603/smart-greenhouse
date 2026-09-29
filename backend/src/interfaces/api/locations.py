from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.application.locations.config_service import LocationConfigService
from src.application.locations.dto import (
    LocationConfigCreateRequest,
    LocationConfigResponse,
)
from src.application.locations.mappers import location_config_to_dto
from src.domain.locations.errors import ConfigurationError, LocationNotFoundError
from src.infrastructure.db import get_db
from src.infrastructure.persistence.location_repository import LocationRepository

router = APIRouter(prefix="/api/locations", tags=["locations"])


def get_config_service(db: Session = Depends(get_db)) -> LocationConfigService:
    return LocationConfigService(LocationRepository(db))


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