import logging
from datetime import datetime
from typing import Callable
from uuid import UUID

from src.domain.actuators.ports import ActuatorPort, AppliedCommand
from src.domain.sensors.reading import utc_now

logger = logging.getLogger(__name__)


class SimulationActuatorAdapter(ActuatorPort):
    """Records commands in memory and logs them. No GPIO, no real hardware."""

    def __init__(self, clock: Callable[[], datetime] = utc_now) -> None:
        self._clock = clock
        self.applied: list[AppliedCommand] = []

    def apply(self, device_id: UUID, command: str, payload: dict) -> AppliedCommand:
        record = AppliedCommand(
            device_id=device_id,
            command=command,
            payload=dict(payload),
            applied_at=self._clock(),
        )
        self.applied.append(record)
        logger.info("Simulated actuator %s: %s %s", device_id, command, payload)
        return record