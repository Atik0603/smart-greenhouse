from datetime import datetime
from uuid import UUID

from src.application.alerts.dto import AlertDto
from src.infrastructure.persistence.alert_repository import AlertRepository

STATUS_FILTERS = {"active": "active", "resolved": "resolved", "all": None}


class InvalidAlertFilterError(ValueError):
    """Unknown status filter (HTTP 400)."""


class AlertQueryService:
    def __init__(self, alerts: AlertRepository) -> None:
        self._alerts = alerts

    def list(
        self,
        status: str = "active",
        location_id: UUID | None = None,
        zone_id: UUID | None = None,
        since: datetime | None = None,
        limit: int = 50,
    ) -> list[AlertDto]:
        if status not in STATUS_FILTERS:
            raise InvalidAlertFilterError(
                f"Unknown status '{status}'. Use one of: {', '.join(STATUS_FILTERS)}"
            )
        records = self._alerts.list(
            status=STATUS_FILTERS[status],
            location_id=location_id,
            zone_id=zone_id,
            since=since,
            limit=limit,
        )
        return [AlertDto(**r.__dict__) for r in records]