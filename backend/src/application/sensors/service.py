from sqlalchemy.orm import Session

from src.domain.sensors.creators import SENSOR_CREATORS
from src.domain.sensors.entity import Sensor
from src.infrastructure.persistence.device_repository import DeviceRepository


class UnknownSensorTypeError(ValueError):
    pass


class SensorService:
    def __init__(self, db: Session) -> None:
        self.repository = DeviceRepository(db)

    def create_sensor(self, type_key: str, display_name: str) -> Sensor:
        creator = SENSOR_CREATORS.get(type_key)
        if creator is None:
            raise UnknownSensorTypeError(f"unsupported sensor type: {type_key}")
        sensor = creator.create_sensor(display_name)
        return self.repository.save(sensor)

    def list_sensors(self) -> list[Sensor]:
        return self.repository.list_sensors()