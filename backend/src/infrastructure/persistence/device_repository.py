from sqlalchemy.orm import Session

from src.domain.devices.entity import Device
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
            device_family="simulation",
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

        # --- Phase 3: devices (sensors + actuators) ---

    def save_devices(self, devices: list[Device]) -> list[Device]:
        rows = [self._device_to_row(d) for d in devices]
        self.db.add_all(rows)
        self.db.commit()
        for row in rows:
            self.db.refresh(row)
        return [self._row_to_device(row) for row in rows]

    def save_device(self, device: Device) -> Device:
        return self.save_devices([device])[0]

    def list_devices(
        self, family: str | None = None, role: str | None = None
    ) -> list[Device]:
        query = self.db.query(DeviceRow)
        if family is not None:
            query = query.filter(DeviceRow.device_family == family)
        if role is not None:
            query = query.filter(DeviceRow.role == role)
        rows = query.order_by(DeviceRow.created_at.desc()).all()
        return [self._row_to_device(row) for row in rows]

    def _device_to_row(self, device: Device) -> DeviceRow:
        return DeviceRow(
            device_type=device.device_type,
            role=device.role,
            device_family=device.device_family,
            display_name=device.display_name,
            default_config=device.default_config,
        )

    def _row_to_device(self, row: DeviceRow) -> Device:
        return Device(
            id=row.id,
            device_type=row.device_type,
            role=row.role,
            device_family=row.device_family,
            display_name=row.display_name or "",
            default_config=row.default_config,
        )