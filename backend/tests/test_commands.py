import uuid
from datetime import datetime, timezone

import pytest

from src.domain.actuators.ports import ActuatorPort, AppliedCommand
from src.domain.commands.base import Command
from src.domain.commands.errors import InvalidCommandPayloadError, UnknownCommandError
from src.domain.commands.invoker import CommandInvoker, command_for, command_types
from src.domain.commands.light import SetLightLevelCommand
from src.domain.commands.pump import StartPumpCommand, StopPumpCommand

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
DEVICE = uuid.uuid4()


class SpyPort(ActuatorPort):
    def __init__(self) -> None:
        self.calls: list = []

    def apply(self, device_id, command, payload):
        self.calls.append((device_id, command, payload))
        return AppliedCommand(device_id=device_id, command=command, payload=dict(payload), applied_at=NOW)


# --- Registry ---

@pytest.mark.parametrize(
    "command_type, cls",
    [
        ("start_pump", StartPumpCommand),
        ("stop_pump", StopPumpCommand),
        ("set_light_level", SetLightLevelCommand),
    ],
)
def test_registry_maps_type_to_class(command_type, cls):
    command = command_for(command_type, DEVICE)
    assert isinstance(command, cls)
    assert command.command_type == command_type
    assert command.device_id == DEVICE


def test_unknown_type_is_rejected_by_the_registry():
    with pytest.raises(UnknownCommandError, match="dance"):
        command_for("dance", DEVICE)


def test_command_types_are_listed():
    assert command_types() == ["set_light_level", "start_pump", "stop_pump"]


# --- Each command knows what it sends and where the lifecycle goes ---

@pytest.mark.parametrize(
    "command_type, payload, sent, target",
    [
        ("start_pump", {}, ("start_pump", {}), "running"),
        ("stop_pump", {}, ("stop_pump", {}), "idle"),
        ("set_light_level", {"level": 40}, ("set_light_level", {"level": 40}), "running"),
    ],
)
def test_execute_sends_the_right_request(command_type, payload, sent, target):
    port = SpyPort()
    command = command_for(command_type, DEVICE, payload)

    result = CommandInvoker().run(command, port)

    assert port.calls == [(DEVICE, *sent)]
    assert result.command == sent[0]
    assert command.target_state == target


# --- set_light_level payload ---

def test_light_level_defaults_to_one():
    command = command_for("set_light_level", DEVICE)
    assert command.payload == {"level": 1}


@pytest.mark.parametrize("level", [-1, 101, "bright", True, None])
def test_invalid_light_level_is_refused_when_the_command_is_built(level):
    with pytest.raises(InvalidCommandPayloadError):
        command_for("set_light_level", DEVICE, {"level": level})


# --- The invoker does not care which command it runs ---

def test_invoker_runs_any_command_without_knowing_its_type():
    class PingCommand(Command):
        command_type = "ping"

        def execute(self, port):
            return port.apply(self.device_id, "ping", {})

    port = SpyPort()
    CommandInvoker().run(PingCommand(DEVICE), port)
    assert port.calls == [(DEVICE, "ping", {})]


def test_command_interface_requires_execute():
    class Broken(Command):
        command_type = "broken"

    with pytest.raises(TypeError):
        Broken(DEVICE)