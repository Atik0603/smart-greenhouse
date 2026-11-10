import uuid
from datetime import datetime, timedelta, timezone

import pytest

from src.domain.actuators.errors import PolicyViolationError
from src.domain.actuators.ports import ActuatorPort, AppliedCommand
from src.infrastructure.adapters.actuators.logging_decorator import LoggingActuatorDecorator
from src.infrastructure.adapters.actuators.max_runtime_decorator import MaxRunTimeActuatorDecorator
from src.infrastructure.adapters.actuators.simulation import SimulationActuatorAdapter

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
DEVICE = uuid.uuid4()


# --- test doubles ---

class SpyPort(ActuatorPort):
    """Innermost stand-in: records every call it receives."""

    def __init__(self, fail: Exception | None = None) -> None:
        self.calls: list = []
        self.fail = fail

    def apply(self, device_id, command, payload):
        self.calls.append((device_id, command, payload))
        if self.fail:
            raise self.fail
        return AppliedCommand(
            device_id=device_id, command=command, payload=dict(payload), applied_at=NOW
        )


class FakeLog:
    def __init__(self) -> None:
        self.rows: list = []

    def add(self, device_id, success, policy_applied, message):
        self.rows.append((device_id, success, list(policy_applied), message))


def running_for(minutes):
    return lambda _device_id: ("running", NOW - timedelta(minutes=minutes))


def max_runtime(inner, lookup):
    return MaxRunTimeActuatorDecorator(inner, lookup, clock=lambda: NOW)


def stack(lookup):
    """The production order: Logging → MaxRunTime → inner."""
    inner, log = SpyPort(), FakeLog()
    return LoggingActuatorDecorator(max_runtime(inner, lookup), log), inner, log


# --- Max run time ---

def test_max_runtime_does_not_call_inner():
    inner = SpyPort()
    with pytest.raises(PolicyViolationError) as info:
        max_runtime(inner, running_for(31)).apply(DEVICE, "stop_pump", {})

    assert inner.calls == []                       # the inner adapter was never reached
    assert info.value.policy == "maxRunTime"
    assert str(info.value) == "Max run time exceeded"


@pytest.mark.parametrize("minutes, blocked", [(29, False), (30, True), (31, True)])
def test_max_runtime_limit_is_at_least_thirty_minutes(minutes, blocked):
    inner = SpyPort()
    decorated = max_runtime(inner, running_for(minutes))
    if blocked:
        with pytest.raises(PolicyViolationError):
            decorated.apply(DEVICE, "x", {})
        assert inner.calls == []
    else:
        decorated.apply(DEVICE, "x", {})
        assert len(inner.calls) == 1


@pytest.mark.parametrize(
    "lookup",
    [
        lambda _: None,                                         # never transitioned: no row
        lambda _: ("idle", NOW - timedelta(hours=5)),           # idle for hours
        lambda _: ("maintenance", NOW - timedelta(hours=5)),
    ],
)
def test_max_runtime_only_applies_to_running(lookup):
    inner = SpyPort()
    max_runtime(inner, lookup).apply(DEVICE, "x", {})
    assert len(inner.calls) == 1


# --- Logging ---

def test_logging_records_success_and_returns_the_inner_result():
    inner, log = SpyPort(), FakeLog()
    result = LoggingActuatorDecorator(inner, log).apply(DEVICE, "anything", {"duration_s": 10})

    assert result == AppliedCommand(
        device_id=DEVICE, command="anything", payload={"duration_s": 10}, applied_at=NOW
    )
    assert log.rows == [(DEVICE, True, ["logging"], None)]


def test_unexpected_adapter_error_is_logged_and_reraised():
    inner, log = SpyPort(fail=RuntimeError("relay offline")), FakeLog()
    with pytest.raises(RuntimeError):
        LoggingActuatorDecorator(inner, log).apply(DEVICE, "x", {})
    assert log.rows == [(DEVICE, False, ["logging"], "relay offline")]


# --- The full stack ---

def test_failed_policy_writes_execution_row():
    port, inner, log = stack(running_for(31))

    with pytest.raises(PolicyViolationError):
        port.apply(DEVICE, "stop_pump", {})

    assert inner.calls == []
    assert log.rows == [(DEVICE, False, ["maxRunTime", "logging"], "Max run time exceeded")]


def test_unknown_command_still_succeeds_through_the_stack():
    port, inner, log = stack(lambda _: ("idle", NOW))
    port.apply(DEVICE, "not_a_real_command", {})

    assert len(inner.calls) == 1                   # commands are not validated in this phase
    assert log.rows == [(DEVICE, True, ["logging"], None)]


def test_real_simulation_adapter_is_reached_through_the_stack():
    sim, log = SimulationActuatorAdapter(clock=lambda: NOW), FakeLog()
    port = LoggingActuatorDecorator(max_runtime(sim, lambda _: None), log)

    result = port.apply(DEVICE, "start_pump", {})

    assert isinstance(port, ActuatorPort)          # the caller only sees "a port"
    assert sim.applied == [result]                 # the innermost adapter did the work


def test_wrong_order_loses_the_blocked_attempt():
    """Why logging must be outermost: inside max-run-time it never sees a blocked call."""
    inner, log = SpyPort(), FakeLog()
    wrong = max_runtime(LoggingActuatorDecorator(inner, log), running_for(31))

    with pytest.raises(PolicyViolationError):
        wrong.apply(DEVICE, "stop_pump", {})

    assert log.rows == []                          # no row: the attempt is invisible