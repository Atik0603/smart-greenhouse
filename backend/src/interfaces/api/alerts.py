from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.application.alerts.dto import AlertDto
from src.application.alerts.service import AlertQueryService, InvalidAlertFilterError
from src.infrastructure.db import get_db
from src.infrastructure.persistence.alert_repository import AlertRepository

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


def get_alert_service(db: Session = Depends(get_db)) -> AlertQueryService:
    return AlertQueryService(AlertRepository(db))


@router.get(
    "",
    response_model=list[AlertDto],
    responses={400: {"description": "Unknown status filter"}},
    summary="Alerts, newest first (default status=active)",
)
def list_alerts(
    status_filter: str = Query(
        default="active", alias="status", description="active, resolved or all"
    ),
    location_id: UUID | None = Query(default=None),
    zone_id: UUID | None = Query(default=None),
    since: datetime | None = Query(
        default=None, description="Only alerts created at or after this time (ISO 8601)"
    ),
    limit: int = Query(default=50, ge=1, le=200, description="How many rows (1–200)"),
    service: AlertQueryService = Depends(get_alert_service),
) -> list[AlertDto]:
    try:
        return service.list(status_filter, location_id, zone_id, since, limit)
    except InvalidAlertFilterError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc