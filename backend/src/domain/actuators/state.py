from abc import ABC, abstractmethod

from src.domain.actuators.errors import UnknownStateError

INITIAL_STATE = "idle"


class ActuatorState(ABC):
    """One lifecycle state. It knows where it may go and which commands lead there."""

    name: str

    @abstractmethod
    def transitions(self) -> dict[str, str | None]:
        """target state -> generic command that causes the move.
        None means a system event (nobody presses a button for it)."""

    def can_move_to(self, target: str) -> bool:
        return target in self.transitions()

    def legal_targets(self) -> list[str]:
        return list(self.transitions())

    def user_commands(self) -> list[str]:
        return [cmd for cmd in self.transitions().values() if cmd is not None]


class OffState(ActuatorState):
    name = "off"

    def transitions(self) -> dict[str, str | None]:
        return {"idle": "power_on"}


class IdleState(ActuatorState):
    name = "idle"

    def transitions(self) -> dict[str, str | None]:
        return {
            "running": "start",
            "maintenance": "begin_maintenance",
            "off": "power_off",
            "error": None,
        }


class RunningState(ActuatorState):
    name = "running"

    def transitions(self) -> dict[str, str | None]:
        return {"idle": "stop", "error": None}


class MaintenanceState(ActuatorState):
    name = "maintenance"

    def transitions(self) -> dict[str, str | None]:
        return {"idle": "end_maintenance", "error": None}


class ErrorState(ActuatorState):
    name = "error"

    def transitions(self) -> dict[str, str | None]:
        return {"idle": "reset", "maintenance": "begin_maintenance"}


# --- Registry: the ONE place that maps a stored name to a state object ---

_STATES: dict[str, ActuatorState] = {
    s.name: s
    for s in (OffState(), IdleState(), RunningState(), MaintenanceState(), ErrorState())
}


def get_state(name: str) -> ActuatorState:
    try:
        return _STATES[name]
    except KeyError:
        raise UnknownStateError(
            f"Unknown state '{name}'. Known states: {', '.join(_STATES)}"
        ) from None


def state_names() -> list[str]:
    return list(_STATES)