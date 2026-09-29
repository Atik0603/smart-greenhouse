from abc import ABC, abstractmethod

from src.domain.devices.entity import Device
from src.domain.sensors.creators import SENSOR_CREATORS
from src.domain.sensors.entity import Sensor


class UnknownDeviceFamilyError(Exception):
    def __init__(self, family: str) -> None:
        super().__init__(f"Unknown device family: {family}")
        self.family = family


def _sensor_as_device(sensor: Sensor, family: str, extra_config: dict) -> Device:
    """Turn a Phase 2 Sensor into a Device tagged with a family."""
    return Device(
        device_type=sensor.device_type,
        role="sensor",
        device_family=family,
        display_name=sensor.display_name,
        default_config={**sensor.default_config, **extra_config},
    )


# --- Abstract factory ---

class DeviceFamilyFactory(ABC):
    family_key: str

    @abstractmethod
    def create_sensors(self) -> list[Device]:
        ...

    @abstractmethod
    def create_actuators(self) -> list[Device]:
        ...

    def create_device_set(self) -> list[Device]:
        """The whole kit: always sensors AND actuators from this one family."""
        return self.create_sensors() + self.create_actuators()


# --- Concrete factory: simulation ---

class SimulationDeviceFactory(DeviceFamilyFactory):
    family_key = "simulation"

    def create_sensors(self) -> list[Device]:
        extra = {"protocol": "simulated", "value_source": "random_walk"}
        return [
            _sensor_as_device(SENSOR_CREATORS["moisture"].create_sensor("Sim moisture sensor"), self.family_key, extra),
            _sensor_as_device(SENSOR_CREATORS["light"].create_sensor("Sim light sensor"), self.family_key, extra),
        ]

    def create_actuators(self) -> list[Device]:
        return [
            Device(
                device_type="water_pump",
                role="actuator",
                device_family=self.family_key,
                display_name="Sim water pump",
                default_config={"protocol": "simulated", "flow_rate_lpm": 2.0, "max_run_seconds": 30},
            ),
            Device(
                device_type="grow_light",
                role="actuator",
                device_family=self.family_key,
                display_name="Sim grow light",
                default_config={"protocol": "simulated", "brightness_percent": 80},
            ),
        ]


# --- Concrete factory: edge ---

class EdgeDeviceFactory(DeviceFamilyFactory):
    family_key = "edge"

    def create_sensors(self) -> list[Device]:
        extra = {"protocol": "i2c", "bus": 1}
        return [
            _sensor_as_device(SENSOR_CREATORS["moisture"].create_sensor("Edge moisture probe"), self.family_key, extra),
            _sensor_as_device(SENSOR_CREATORS["light"].create_sensor("Edge light meter"), self.family_key, extra),
        ]

    def create_actuators(self) -> list[Device]:
        return [
            Device(
                device_type="water_pump",
                role="actuator",
                device_family=self.family_key,
                display_name="Edge pump relay",
                default_config={"protocol": "gpio", "gpio_pin": 17, "max_run_seconds": 20},
            ),
            Device(
                device_type="grow_light",
                role="actuator",
                device_family=self.family_key,
                display_name="Edge LED panel",
                default_config={"protocol": "gpio", "gpio_pin": 27, "pwm": True},
            ),
        ]


# --- Registry ---

DEVICE_FAMILY_FACTORIES: dict[str, DeviceFamilyFactory] = {
    "simulation": SimulationDeviceFactory(),
    "edge": EdgeDeviceFactory(),
}


def get_family_factory(family: str) -> DeviceFamilyFactory:
    factory = DEVICE_FAMILY_FACTORIES.get(family)
    if factory is None:
        raise UnknownDeviceFamilyError(family)
    return factory