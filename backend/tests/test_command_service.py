import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from src.application.commands.service import CommandService
from src.domain.actuators.errors import PolicyViolationError
from src.domain.actuators.ports import ActuatorPort, AppliedCommand
from src.domain.commands.errors import UnknownCommandError
from src.domain.devices.errors import DeviceNotFoundError
from src.infrastructure.persistence.command_log_repository import CommandLogRecord

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def device(role="actuator", device_type="water_pump"):
    return SimpleNamespace(
        id=uuid.uuid4(), role=role, device_type=device_type, location_id=None, zone_id=None
    )


class FakeDevices:
    def __init__(self, *devices):
        self.by_id = {d.id: d for d in devices}

    def get_device(self, device_id):
        return self.by_id.get(device_id)


class FakeStates:
    def __init__(self, stored=None):
        self.stored = dict(stored or {})
        self.saves = []

    def get_state(self, device_id):
        return self.stored.get(device_id, "idle")

    def save_state(self, device_id, state):
        self.saves.append((device_id, state))
        self.stored[device_id] = state


class SpyPort(ActuatorPort):
    def __init__(self, fail=None):
        self.calls = []
        self.fail = fail

    def apply(self, device_id, command, payload):
        self.calls.append((device_id, command, payload))
        if self.fail:
            raise self.fail
        return AppliedCommand(device_id=device_id, command=command, payload=dict(payload), applied_at=NOW)


class FakeCommandLog:
    def __init__(self):
        self.rows = []

    def add(self, command_type, device_id, payload, status, error_message=None):
        record = CommandLogRecord(
            id=uuid.uuid4(), command_type=command_type, device_id=device_id,
            payload=dict(payload), status=status, error_message=error_message, created_at=NOW,
        )
        self.rows.append(record)
        return record


def service(dev, stored=None, port=None):
    states, port, log = FakeStates(stored), port or SpyPort(), FakeCommandLog()
    return CommandService(FakeDevices(dev), states, port, log), states, port, log


# --- rejected: guard stops everything except the log ---

def test_rejected_command_does_not_apply_or_change_state():
    pump = device()
    svc, states, port, log = service(pump)                       # stored: idle

    result = svc.submit("stop_pump", pump.id, {})

    assert result.status == "rejected"
    assert "while the actuator is idle" in result.error_message
    assert port.calls == []                                      # never reached the port
    assert states.saves == []                                    # state untouched
    assert [r.status for r in log.rows] == ["rejected"]


def test_command_for_the_wrong_device_type_is_rejected():
    pump = device()
    svc, _, port, _ = service(pump)
    assert svc.submit("set_light_level", pump.id, {}).status == "rejected"
    assert port.calls == []


# --- success: apply, transition, log ---

def test_start_pump_applies_then_transitions_to_running():
    pump = device()
    svc, states, port, log = service(pump)

    result = svc.submit("start_pump", pump.id, {})

    assert result.status == "success"
    assert port.calls == [(pump.id, "start_pump", {})]
    assert states.saves == [(pump.id, "running")]
    assert [r.status for r in log.rows] == ["success"]


def test_set_light_level_on_a_running_light_does_not_transition():
    light = device(device_type="grow_light")
    svc, states, port, _ = service(light, stored={light.id: "running"})

    assert svc.submit("set_light_level", light.id, {"level": 60}).status == "success"
    assert port.calls == [(light.id, "set_light_level", {"level": 60})]
    assert states.saves == []                                    # target == current


# --- failed: accepted, attempted, stopped by a policy ---

def test_policy_failure_is_logged_failed_and_state_unchanged():
    pump = device()
    port = SpyPort(fail=PolicyViolationError("maxRunTime", "Max run time exceeded"))
    svc, states, _, log = service(pump, stored={pump.id: "running"}, port=port)

    result = svc.submit("stop_pump", pump.id, {})

    assert result.status == "failed"
    assert result.error_message == "Max run time exceeded"
    assert states.saves == []
    assert [r.status for r in log.rows] == ["failed"]


# --- no row at all ---

def test_unknown_type_writes_no_row():
    pump = device()
    svc, _, port, log = service(pump)
    with pytest.raises(UnknownCommandError):
        svc.submit("dance", pump.id, {})
    assert log.rows == [] and port.calls == []


@pytest.mark.parametrize("dev", [None, device(role="sensor", device_type="moisture_sensor")])
def test_missing_device_or_sensor_is_not_found(dev):
    target = dev or device()
    svc, _, _, log = service(dev or device())
    with pytest.raises(DeviceNotFoundError):
        svc.submit("start_pump", target.id if dev else uuid.uuid4(), {})
    assert log.rows == []