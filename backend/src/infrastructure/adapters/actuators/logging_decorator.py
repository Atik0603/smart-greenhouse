from uuid import UUID

from src.domain.actuators.errors import PolicyViolationError
from src.domain.actuators.ports import ActuatorPort, AppliedCommand


class LoggingActuatorDecorator(ActuatorPort):
    """Outermost wrapper: every attempt, successful or not, leaves one execution row."""

    def __init__(self, inner: ActuatorPort, log_repo) -> None:
        self._inner = inner
        self._log = log_repo      # anything with add(device_id, success, policy_applied, message)

    def apply(self, device_id: UUID, command: str, payload: dict) -> AppliedCommand:
        try:
            result = self._inner.apply(device_id, command, payload)
        except PolicyViolationError as exc:
            self._log.add(device_id, False, [exc.policy, "logging"], exc.message)
            raise
        except Exception as exc:
            self._log.add(device_id, False, ["logging"], str(exc))
            raise
        self._log.add(device_id, True, ["logging"], None)
        return result