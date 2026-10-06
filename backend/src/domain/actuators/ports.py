from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class AppliedCommand:
    device_id: UUID
    command: str                       # e.g. "on", "off", "set_brightness"
    payload: dict = field(default_factory=dict)
    applied_at: datetime | None = None


class ActuatorPort(ABC):
    @abstractmethod
    def apply(self, device_id: UUID, command: str, payload: dict) -> AppliedCommand:
        """Send a command to an actuator and report what was applied."""
        ...
        