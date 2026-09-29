from uuid import UUID

from sqlalchemy.orm import Session

from src.domain.locations.entity import Location, LocationConfig, Zone, LocationSummary
from src.infrastructure.persistence.models import LocationRow, ZoneRow


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