from sqlalchemy.orm import Session

from src.domain.sensors.entity import Sensor
from src.infrastructure.persistence.models import DeviceRow


class DeviceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def save(self, sensor: Sensor) -> Sensor:
        row = DeviceRow(
            device_type=sensor.device_type,
            display_name=sensor.display_name,
            default_config=sensor.default_config,
            role="sensor",
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self._to_entity(row)

    def list_sensors(self) -> list[Sensor]:
        rows = (
            self.db.query(DeviceRow)
            .filter(DeviceRow.role == "sensor")
            .order_by(DeviceRow.created_at.desc())
            .all()
        )
        return [self._to_entity(row) for row in rows]

    def _to_entity(self, row: DeviceRow) -> Sensor:
        return Sensor(
            id=row.id,
            device_type=row.device_type,
            display_name=row.display_name,
            default_config=row.default_config,
        )