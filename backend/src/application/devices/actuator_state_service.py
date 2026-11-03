from dataclasses import dataclass
from uuid import UUID

from src.domain.actuators.context import ActuatorContext
from src.domain.actuators.errors import NotAnActuatorError
from src.domain.devices.entity import Device
from src.domain.devices.errors import DeviceNotFoundError
from src.infrastructure.persistence.actuator_state_repository import ActuatorStateRepository
from src.infrastructure.persistence.device_repository import DeviceRepository


@dataclass(frozen=True)
class ActuatorStateView:
    state: str
    allowed_commands: list[str]


class ActuatorStateService:
    def __init__(self, devices: DeviceRepository, states: ActuatorStateRepository) -> None:
        self._devices = devices
        self._states = states

    def views_for(self, devices: list[Device]) -> dict[UUID, ActuatorStateView]:
        """State + allowed commands for every actuator in the list (one state query)."""
        actuators = [d for d in devices if d.role == "actuator"]
        stored = self._states.get_states([d.id for d in actuators])
        return {
            d.id: self._view(d.device_type, stored.get(d.id, "idle")) for d in actuators
        }

    def get(self, device_id: UUID) -> ActuatorStateView:
        device = self._require_actuator(device_id)
        return self._view(device.device_type, self._states.get_state(device_id))

    def transition(self, device_id: UUID, target: str) -> ActuatorStateView:
        device = self._require_actuator(device_id)
        context = ActuatorContext(device.device_type, self._states.get_state(device_id))
        context.transition(target)                    # illegal → raises, nothing below runs
        self._states.save_state(device_id, context.state)
        return ActuatorStateView(context.state, context.allowed_commands())

    # --- helpers ---

    def _require_actuator(self, device_id: UUID) -> Device:
        device = self._devices.get_device(device_id)
        if device is None:
            raise DeviceNotFoundError(device_id)
        if device.role != "actuator":
            raise NotAnActuatorError(f"Device {device_id} is a {device.role}, not an actuator")
        return device

    @staticmethod
    def _view(device_type: str, state: str) -> ActuatorStateView:
        context = ActuatorContext(device_type, state)
        return ActuatorStateView(context.state, context.allowed_commands())