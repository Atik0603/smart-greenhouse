from uuid import UUID

from src.application.commands.dto import CommandLogDto
from src.domain.actuators.context import ActuatorContext
from src.domain.actuators.errors import PolicyViolationError
from src.domain.actuators.ports import ActuatorPort
from src.domain.commands.base import Command
from src.domain.commands.invoker import CommandInvoker, command_for
from src.domain.devices.errors import DeviceNotFoundError
from src.infrastructure.persistence.actuator_state_repository import ActuatorStateRepository
from src.infrastructure.persistence.command_log_repository import CommandLogRepository
from src.infrastructure.persistence.device_repository import DeviceRepository

MAX_LIMIT = 200


class CommandService:
    def __init__(
        self,
        devices: DeviceRepository,
        states: ActuatorStateRepository,
        port: ActuatorPort,
        log: CommandLogRepository,
        invoker: CommandInvoker | None = None,
    ) -> None:
        self._devices = devices
        self._states = states
        self._port = port
        self._log = log
        self._invoker = invoker or CommandInvoker()

    def submit(self, command_type: str, device_id: UUID, payload: dict) -> CommandLogDto:
        # 1. Only real actuators can receive commands (404, no row)
        device = self._devices.get_device(device_id)
        if device is None or device.role != "actuator":
            raise DeviceNotFoundError(device_id)

        # 2. Unknown type / bad payload → raises before any row is written (400)
        command = command_for(command_type, device_id, payload)

        # 3. Guard: is this command legal in the saved state?
        context = ActuatorContext(device.device_type, self._states.get_state(device_id))
        allowed = context.allowed_commands()
        if command.command_type not in allowed:
            return self._record(
                command,
                "rejected",
                f"'{command.command_type}' is not allowed while the actuator is "
                f"{context.state}. Allowed: {', '.join(allowed) or 'none'}",
            )

        # 4. Execute through the decorated port (Logging → MaxRunTime → Simulation)
        try:
            self._invoker.run(command, self._port)
        except PolicyViolationError as exc:
            return self._record(command, "failed", exc.message)
        except Exception as exc:                       # adapter error after acceptance
            return self._record(command, "failed", str(exc))

        # 5. Completed: move the lifecycle only if the target differs
        if command.target_state and command.target_state != context.state:
            context.transition(command.target_state)
            self._states.save_state(device_id, context.state)

        return self._record(command, "success", None)

    def list_recent(self, limit: int = 50) -> list[CommandLogDto]:
        limit = max(1, min(limit, MAX_LIMIT))
        return [CommandLogDto(**r.__dict__) for r in self._log.list_recent(limit)]

    def _record(self, command: Command, status: str, error: str | None) -> CommandLogDto:
        record = self._log.add(
            command.command_type, command.device_id, command.payload, status, error
        )
        return CommandLogDto(**record.__dict__)