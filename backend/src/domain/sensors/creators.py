from abc import ABC, abstractmethod

from src.domain.sensors.entity import Sensor


class SensorCreator(ABC):
    @abstractmethod
    def create_sensor(self, display_name: str) -> Sensor:
        """Factory method: each concrete creator knows its own type + defaults."""
        ...


class MoistureSensorCreator(SensorCreator):
    def create_sensor(self, display_name: str) -> Sensor:
        return Sensor(
            device_type="moisture_sensor",
            display_name=display_name,
            default_config={
                "unit": "percent",
                "sampling_interval_seconds": 60,
                "moisture_threshold": 30,
            },
        )


class LightSensorCreator(SensorCreator):
    def create_sensor(self, display_name: str) -> Sensor:
        return Sensor(
            device_type="light_sensor",
            display_name=display_name,
            default_config={
                "unit": "lux",
                "sampling_interval_seconds": 300,
            },
        )


SENSOR_CREATORS: dict[str, SensorCreator] = {
    "moisture": MoistureSensorCreator(),
    "light": LightSensorCreator(),
}