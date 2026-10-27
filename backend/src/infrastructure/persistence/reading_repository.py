from datetime import datetime
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.domain.sensors.reading import Reading
from src.infrastructure.persistence.models import ReadingRow


class ReadingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, reading: Reading) -> Reading:
        row = ReadingRow(
            device_id=reading.device_id,
            value=reading.value,
            unit=reading.unit,
            source=reading.source,
            recorded_at=reading.recorded_at,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self._to_reading(row)

    def list_recent(self, device_id: UUID, limit: int) -> list[Reading]:
        rows = (
            self.db.query(ReadingRow)
            .filter(ReadingRow.device_id == device_id)
            .order_by(ReadingRow.recorded_at.desc())
            .limit(limit)
            .all()
        )
        return [self._to_reading(row) for row in rows]

    def latest_recorded_at_by_device(self, device_ids: list[UUID]) -> dict[UUID, datetime]:
        if not device_ids:
            return {}
        rows = (
            self.db.query(ReadingRow.device_id, func.max(ReadingRow.recorded_at))
            .filter(ReadingRow.device_id.in_(device_ids))
            .group_by(ReadingRow.device_id)
            .all()
        )
        return {device_id: latest for device_id, latest in rows}

    def latest_by_device(self, device_ids: list[UUID]) -> dict[UUID, Reading]:
        """Newest reading per device id (any source). Devices without readings are absent."""
        if not device_ids:
            return {}
        rows = (
            self.db.query(ReadingRow)
            .filter(ReadingRow.device_id.in_(device_ids))
            .distinct(ReadingRow.device_id)
            .order_by(ReadingRow.device_id, ReadingRow.recorded_at.desc())
            .all()
        )
        return {row.device_id: self._to_reading(row) for row in rows}

    def _to_reading(self, row: ReadingRow) -> Reading:
        return Reading(
            device_id=row.device_id,
            value=row.value,
            unit=row.unit,
            source=row.source,
            recorded_at=row.recorded_at,
        )