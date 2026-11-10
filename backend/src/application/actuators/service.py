from uuid import UUID

from src.application.actuators.dto import AppliedCommandDto, ExecutionDto
from src.domain.actuators.errors import NotAnActuatorError
from src.domain.actuators.ports import ActuatorPort
from src.domain.devices.errors import DeviceNotFoundError
from src.infrastructure.persistence.device_repository import DeviceRepository
from src.infrastructure.persistence.execution_log_repository import ExecutionLogRepository

MAX_LIMIT = 200


class ActuatorExecutionService:
    def __init__(
        self, port: ActuatorPort, devices: DeviceRepository, log: ExecutionLogRepository
    ) -> None:
        self._port = port
        self._devices = devices
        self._log = log

    def apply(self, device_id: UUID, command: str, payload: dict) -> AppliedCommandDto:
        device = self._devices.get_device(device_id)
        if device is None:
            raise DeviceNotFoundError(device_id)
        if device.role != "actuator":
            raise NotAnActuatorError(f"Device {device_id} is a {device.role}, not an actuator")

        result = self._port.apply(device_id, command, payload)   # through the whole stack
        return AppliedCommandDto(
            device_id=result.device_id,
            command=result.command,
            payload=result.payload,
            applied_at=result.applied_at,
        )

    def list_recent(self, limit: int = 20) -> list[ExecutionDto]:
        limit = max(1, min(limit, MAX_LIMIT))
        return [ExecutionDto(**record.__dict__) for record in self._log.list_recent(limit)]