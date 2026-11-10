from datetime import datetime, timedelta
from typing import Callable
from uuid import UUID

from src.domain.actuators.errors import PolicyViolationError
from src.domain.actuators.ports import ActuatorPort, AppliedCommand
from src.domain.sensors.reading import utc_now

MAX_RUN_TIME = timedelta(minutes=30)
StateLookup = Callable[[UUID], tuple[str, datetime] | None]


class MaxRunTimeActuatorDecorator(ActuatorPort):
    """Refuses commands for an actuator that has been `running` for too long."""

    def __init__(
        self,
        inner: ActuatorPort,
        state_lookup: StateLookup,
        clock: Callable[[], datetime] = utc_now,
        limit: timedelta = MAX_RUN_TIME,
    ) -> None:
        self._inner = inner
        self._state_lookup = state_lookup
        self._clock = clock
        self._limit = limit

    def apply(self, device_id: UUID, command: str, payload: dict) -> AppliedCommand:
        current = self._state_lookup(device_id)
        if current is not None:
            state, since = current
            if state == "running" and self._clock() - since >= self._limit:
                raise PolicyViolationError("maxRunTime", "Max run time exceeded")
        return self._inner.apply(device_id, command, payload)