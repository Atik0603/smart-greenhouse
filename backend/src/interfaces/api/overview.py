from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.application.overview.dto import LocationOverviewDto
from src.application.overview.facade import (
    LocationOverviewFacade,
    build_location_overview_facade,
)
from src.domain.locations.errors import LocationNotFoundError

from src.infrastructure.db import get_db 

router = APIRouter(prefix="/api", tags=["overview"])


def get_overview_facade(db: Session = Depends(get_db)) -> LocationOverviewFacade:
    return build_location_overview_facade(db)


@router.get(
    "/locations/{location_id}/overview",
    response_model=LocationOverviewDto,
    responses={404: {"description": "Location not found"}},
    summary="Dashboard overview: assigned devices, latest readings, strategy and recommendation",
)
def get_location_overview(
    location_id: UUID,
    facade: LocationOverviewFacade = Depends(get_overview_facade),
) -> LocationOverviewDto:
    try:
        return facade.get_overview(location_id)
    except LocationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc