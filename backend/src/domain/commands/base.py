from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.actuators.ports import ActuatorPort, AppliedCommand


class Command(ABC):
    """One operator request as an object: what to do, to which device, with which data."""

    command_type: str
    target_state: str | None = None   # lifecycle state after a completed apply (None = no change)

    def __init__(self, device_id: UUID, payload: dict | None = None) -> None:
        self.device_id = device_id
        self.payload = dict(payload or {})

    @abstractmethod
    def execute(self, port: ActuatorPort) -> AppliedCommand:
        """Carry out the request through the actuator port."""