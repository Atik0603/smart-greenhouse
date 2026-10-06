from abc import ABC, abstractmethod

from src.domain.devices.entity import Device
from src.domain.sensors.reading import Reading


class SensorReadError(Exception):
    """An adapter could not produce a reading (unsupported device, bad payload, push-only device)."""


class SensorPort(ABC):
    @abstractmethod
    def read(self, device: Device) -> Reading:
        """Read one value from the device and return it in the normalized shape."""
        ...