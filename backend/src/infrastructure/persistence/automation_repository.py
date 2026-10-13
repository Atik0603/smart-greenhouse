from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.infrastructure.persistence.models import (
    AutomationRuleRow,
    DeviceRow,
    LocationRow,
    ReadingRow,
    ZoneRow,
)

MOISTURE_SENSOR = "moisture_sensor"
LIGHT_SENSOR = "light_sensor"


@dataclass(frozen=True)
class AutomationRule:
    location_id: UUID
    strategy_key: str
    updated_at: datetime


@dataclass(frozen=True)
class ZoneSnapshot:
    """One zone's thresholds plus its latest readings. Plain values, no ORM."""

    zone_id: UUID
    zone_name: str
    low: float
    high: float
    has_moisture_sensor: bool
    moisture: float | None
    light: float | None


class AutomationRuleRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, location_id: UUID) -> AutomationRule | None:
        row = self._db.scalar(
            select(AutomationRuleRow).where(AutomationRuleRow.location_id == location_id)
        )
        if row is None:
            return None
        return AutomationRule(row.location_id, row.strategy_key, row.updated_at)

    def upsert(self, location_id: UUID, strategy_key: str) -> AutomationRule:
        stmt = (
            insert(AutomationRuleRow)
            .values(location_id=location_id, strategy_key=strategy_key)
            .on_conflict_do_update(
                index_elements=[AutomationRuleRow.location_id],
                set_={"strategy_key": strategy_key, "updated_at": func.now()},
            )
            .returning(AutomationRuleRow.location_id, AutomationRuleRow.strategy_key,
                       AutomationRuleRow.updated_at)
        )
        result = self._db.execute(stmt).one()
        self._db.commit()
        return AutomationRule(result.location_id, result.strategy_key, result.updated_at)


class AutomationContextRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def location_exists(self, location_id: UUID) -> bool:
        return self._db.get(LocationRow, location_id) is not None

    def list_zone_snapshots(self, location_id: UUID) -> list[ZoneSnapshot]:
        zones = self._db.scalars(
            select(ZoneRow).where(ZoneRow.location_id == location_id).order_by(ZoneRow.name)
        ).all()
        return [
            ZoneSnapshot(
                zone_id=zone.id,
                zone_name=zone.name,
                low=zone.moisture_threshold_low,
                high=zone.moisture_threshold_high,
                has_moisture_sensor=self._has_sensor(zone.id, MOISTURE_SENSOR),
                moisture=self._latest_value(zone.id, MOISTURE_SENSOR),
                light=self._latest_value(zone.id, LIGHT_SENSOR),
            )
            for zone in zones
        ]

    def _has_sensor(self, zone_id: UUID, device_type: str) -> bool:
        count = self._db.scalar(
            select(func.count())
            .select_from(DeviceRow)
            .where(DeviceRow.zone_id == zone_id, DeviceRow.device_type == device_type)
        )
        return count > 0

    def _latest_value(self, zone_id: UUID, device_type: str) -> float | None:
        return self._db.scalar(
            select(ReadingRow.value)
            .join(DeviceRow, DeviceRow.id == ReadingRow.device_id)
            .where(DeviceRow.zone_id == zone_id, DeviceRow.device_type == device_type)
            .order_by(ReadingRow.recorded_at.desc())
            .limit(1)
        )