class UnknownStateError(ValueError):
    """The name is not one of the lifecycle states (HTTP 400)."""


class IllegalTransitionError(ValueError):
    """The move is not allowed from the current state (HTTP 409)."""

    def __init__(self, current: str, target: str, legal_targets: list[str]) -> None:
        legal = ", ".join(legal_targets) if legal_targets else "none"
        super().__init__(f"Cannot move from '{current}' to '{target}'. Legal targets: {legal}")
        self.current = current
        self.target = target

class NotAnActuatorError(ValueError):
    """The device exists but is a sensor, so it has no lifecycle (HTTP 400)."""


class PolicyViolationError(Exception):
    """A decorator refused the command. The inner adapter was never called (HTTP 409)."""

    def __init__(self, policy: str, message: str) -> None:
        super().__init__(message)
        self.policy = policy      # e.g. "maxRunTime"
        self.message = message