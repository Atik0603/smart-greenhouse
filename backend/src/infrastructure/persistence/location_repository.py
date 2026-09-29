from uuid import UUID
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.domain.locations.entity import Location, LocationConfig, Zone, LocationSummary
from src.infrastructure.persistence.models import DeviceRow, LocationRow, ZoneRow


class LocationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def save_config(self, config: LocationConfig) -> Location:
        location = config.location
        try:
            location_row = LocationRow(name=location.name)
            self.db.add(location_row)
            self.db.flush()  # Postgres generates location_row.id, not committed yet

            self.db.add_all(
                [
                    ZoneRow(
                        location_id=location_row.id,
                        name=zone.name,
                        moisture_threshold_low=zone.moisture_threshold_low,
                        moisture_threshold_high=zone.moisture_threshold_high,
                        schedule=zone.schedule,
                    )
                    for zone in location.zones
                ]
            )
            self.db.commit()  # location + all zones become permanent together
        except Exception:
            self.db.rollback()  # undo everything from this save
            raise

        saved = self.get_location(location_row.id)
        assert saved is not None
        return saved

    def get_location(self, location_id: UUID) -> Location | None:
        location_row = self.db.get(LocationRow, location_id)
        if location_row is None:
            return None
        zone_rows = (
            self.db.query(ZoneRow)
            .filter(ZoneRow.location_id == location_id)
            .order_by(ZoneRow.name)
            .all()
        )
        return self._to_location(location_row, zone_rows)

    def _to_location(self, row: LocationRow, zone_rows: list[ZoneRow]) -> Location:
        return Location(
            id=row.id,
            name=row.name,
            zones=tuple(self._to_zone(z) for z in zone_rows),
        )

    def _to_zone(self, row: ZoneRow) -> Zone:
        return Zone(
            id=row.id,
            name=row.name,
            moisture_threshold_low=row.moisture_threshold_low,
            moisture_threshold_high=row.moisture_threshold_high,
            schedule=row.schedule,
        )

    def list_locations(self) -> list[LocationSummary]:
        rows = self.db.query(LocationRow).order_by(LocationRow.created_at.desc()).all()
        return [LocationSummary(id=row.id, name=row.name) for row in rows]

    def delete_location(self, location_id: UUID) -> bool:
        row = self.db.get(LocationRow, location_id)
        if row is None:
            return False
        self.db.delete(row)
        self.db.commit()
        return True

    def get_zone(self, zone_id: UUID) -> tuple[Zone, UUID] | None:
        row = self.db.get(ZoneRow, zone_id)
        if row is None:
            return None
        return self._to_zone(row), row.location_id

    def location_exists(self, location_id: UUID) -> bool:
        return self.db.get(LocationRow, location_id) is not None

    def count_zones(self, location_id: UUID) -> int:
        return self.db.query(ZoneRow).filter(ZoneRow.location_id == location_id).count()

    def zone_name_exists(
        self, location_id: UUID, name: str, exclude_zone_id: UUID | None = None
    ) -> bool:
        query = self.db.query(ZoneRow).filter(
            ZoneRow.location_id == location_id,
            func.lower(ZoneRow.name) == name.lower(),
        )
        if exclude_zone_id is not None:
            query = query.filter(ZoneRow.id != exclude_zone_id)
        return query.first() is not None

    def add_zone(self, location_id: UUID, zone: Zone) -> Zone:
        row = ZoneRow(
            location_id=location_id,
            name=zone.name,
            moisture_threshold_low=zone.moisture_threshold_low,
            moisture_threshold_high=zone.moisture_threshold_high,
            schedule=zone.schedule,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self._to_zone(row)

    def update_zone(self, zone: Zone) -> Zone:
        row = self.db.get(ZoneRow, zone.id)
        row.name = zone.name
        row.moisture_threshold_low = zone.moisture_threshold_low
        row.moisture_threshold_high = zone.moisture_threshold_high
        row.schedule = zone.schedule
        self.db.commit()
        self.db.refresh(row)
        return self._to_zone(row)

    def delete_zone_and_unassign(self, zone_id: UUID) -> None:
        try:
            self.db.query(DeviceRow).filter(DeviceRow.zone_id == zone_id).update(
                {DeviceRow.zone_id: None, DeviceRow.location_id: None},
                synchronize_session=False,
            )
            self.db.query(ZoneRow).filter(ZoneRow.id == zone_id).delete(
                synchronize_session=False
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise