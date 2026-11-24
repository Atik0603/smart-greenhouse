from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from src.infrastructure.persistence.models import AlertRow


@dataclass(frozen=True)
class AlertRecord:
    id: UUID
    location_id: UUID | None
    zone_id: UUID | None
    device_id: UUID | None
    severity: str
    message: str
    event_type: str
    status: str
    created_at: datetime


class AlertRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(
        self,
        *,
        severity: str,
        message: str,
        event_type: str,
        device_id: UUID | None,
        location_id: UUID | None,
        zone_id: UUID | None,
    ) -> AlertRecord:
        row = AlertRow(
            severity=severity,
            message=message,
            event_type=event_type,
            device_id=device_id,
            location_id=location_id,
            zone_id=zone_id,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self._to_record(row)

    def list(
        self,
        *,
        status: str | None,
        location_id: UUID | None,
        zone_id: UUID | None,
        since: datetime | None,
        limit: int,
    ) -> list[AlertRecord]:
        query = self.db.query(AlertRow)
        if status is not None:
            query = query.filter(AlertRow.status == status)
        if location_id is not None:
            query = query.filter(AlertRow.location_id == location_id)
        if zone_id is not None:
            query = query.filter(AlertRow.zone_id == zone_id)
        if since is not None:
            query = query.filter(AlertRow.created_at >= since)
        rows = query.order_by(AlertRow.created_at.desc()).limit(limit).all()
        return [self._to_record(row) for row in rows]

    @staticmethod
    def _to_record(row: AlertRow) -> AlertRecord:
        return AlertRecord(
            id=row.id,
            location_id=row.location_id,
            zone_id=row.zone_id,
            device_id=row.device_id,
            severity=row.severity,
            message=row.message,
            event_type=row.event_type,
            status=row.status,
            created_at=row.created_at,
        )