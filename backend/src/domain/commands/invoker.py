from uuid import UUID

from src.domain.actuators.ports import ActuatorPort, AppliedCommand
from src.domain.commands.base import Command
from src.domain.commands.errors import UnknownCommandError
from src.domain.commands.light import SetLightLevelCommand
from src.domain.commands.pump import StartPumpCommand, StopPumpCommand

# --- Registry: the ONE place that maps a type string to a command class ---

_REGISTRY: dict[str, type[Command]] = {
    cls.command_type: cls
    for cls in (StartPumpCommand, StopPumpCommand, SetLightLevelCommand)
}


def command_for(command_type: str, device_id: UUID, payload: dict | None = None) -> Command:
    try:
        command_class = _REGISTRY[command_type]
    except KeyError:
        raise UnknownCommandError(
            f"Unknown command '{command_type}'. Known commands: {', '.join(command_types())}"
        ) from None
    return command_class(device_id, payload)


def command_types() -> list[str]:
    return sorted(_REGISTRY)


class CommandInvoker:
    """Runs any command. It never looks at command_type."""

    def run(self, command: Command, port: ActuatorPort) -> AppliedCommand:
        return command.execute(port)