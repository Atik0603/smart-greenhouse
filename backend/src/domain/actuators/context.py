from src.domain.actuators.errors import IllegalTransitionError
from src.domain.actuators.state import INITIAL_STATE, get_state

# Generic "start"/"stop" get a device-specific name. Phase 10's Command objects reuse these.
COMMAND_NAMES: dict[str, dict[str, str]] = {
    "water_pump": {"start": "start_pump", "stop": "stop_pump"},
    "grow_light": {"start": "lights_on", "stop": "lights_off"},
}


class ActuatorContext:
    """One actuator's lifecycle. Holds the current state object and delegates to it."""

    def __init__(self, device_type: str, state: str = INITIAL_STATE) -> None:
        self._device_type = device_type
        self._state = get_state(state)   # unknown stored name → UnknownStateError

    @property
    def state(self) -> str:
        return self._state.name

    def allowed_commands(self) -> list[str]:
        names = COMMAND_NAMES.get(self._device_type, {})
        return [names.get(cmd, cmd) for cmd in self._state.user_commands()]

    def transition(self, target: str) -> None:
        next_state = get_state(target)
        if not self._state.can_move_to(next_state.name):
            raise IllegalTransitionError(self.state, target, self._state.legal_targets())
        self._state = next_state   # only reached when the move is legal