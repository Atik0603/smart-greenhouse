from uuid import UUID

from src.domain.actuators.ports import ActuatorPort, AppliedCommand
from src.domain.commands.base import Command
from src.domain.commands.errors import InvalidCommandPayloadError

DEFAULT_LEVEL = 1
MIN_LEVEL, MAX_LEVEL = 0, 100


class SetLightLevelCommand(Command):
    command_type = "set_light_level"
    target_state = "running"   # an idle light switches on; a running one just changes level

    def __init__(self, device_id: UUID, payload: dict | None = None) -> None:
        payload = dict(payload or {})
        level = payload.get("level", DEFAULT_LEVEL)
        if isinstance(level, bool) or not isinstance(level, (int, float)):
            raise InvalidCommandPayloadError("set_light_level needs a numeric 'level'")
        if not MIN_LEVEL <= level <= MAX_LEVEL:
            raise InvalidCommandPayloadError(
                f"Light level must be between {MIN_LEVEL} and {MAX_LEVEL} (got {level})"
            )
        super().__init__(device_id, {**payload, "level": level})
        self.level = level

    def execute(self, port: ActuatorPort) -> AppliedCommand:
        return port.apply(self.device_id, self.command_type, {"level": self.level})