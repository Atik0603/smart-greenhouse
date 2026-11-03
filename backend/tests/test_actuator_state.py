import pytest

from src.domain.actuators.context import ActuatorContext
from src.domain.actuators.errors import IllegalTransitionError, UnknownStateError
from src.domain.actuators.state import ActuatorState, get_state, state_names

# The documented legal edges (keep in sync with docs/patterns/state.md)
LEGAL = {
    ("off", "idle"),
    ("idle", "running"),
    ("idle", "maintenance"),
    ("idle", "off"),
    ("idle", "error"),
    ("running", "idle"),
    ("running", "error"),
    ("maintenance", "idle"),
    ("maintenance", "error"),
    ("error", "idle"),
    ("error", "maintenance"),
}

ILLEGAL = sorted(
    {(a, b) for a in state_names() for b in state_names()} - LEGAL
)


# --- Named examples from the guided check ---

def test_idle_to_running_allowed():
    ctx = ActuatorContext("water_pump", "idle")
    ctx.transition("running")
    assert ctx.state == "running"


def test_running_to_maintenance_rejected():
    ctx = ActuatorContext("water_pump", "running")
    with pytest.raises(IllegalTransitionError):
        ctx.transition("maintenance")
    assert ctx.state == "running"


# --- The whole table ---

@pytest.mark.parametrize("source, target", sorted(LEGAL))
def test_every_legal_edge_is_allowed(source, target):
    ctx = ActuatorContext("water_pump", source)
    ctx.transition(target)
    assert ctx.state == target


@pytest.mark.parametrize("source, target", ILLEGAL)
def test_every_other_edge_is_rejected_and_state_unchanged(source, target):
    ctx = ActuatorContext("water_pump", source)
    with pytest.raises(IllegalTransitionError):
        ctx.transition(target)
    assert ctx.state == source


def test_illegal_transition_error_explains_the_legal_targets():
    ctx = ActuatorContext("water_pump", "running")
    with pytest.raises(IllegalTransitionError, match="idle, error") as info:
        ctx.transition("off")
    assert info.value.current == "running"
    assert info.value.target == "off"


def test_unknown_target_is_not_an_illegal_transition():
    with pytest.raises(UnknownStateError, match="nope"):
        ActuatorContext("water_pump", "idle").transition("nope")


def test_unknown_stored_state_is_rejected_when_loading():
    with pytest.raises(UnknownStateError):
        ActuatorContext("water_pump", "runing")


# --- allowed_commands ---

@pytest.mark.parametrize(
    "device_type, state, expected",
    [
        ("water_pump", "idle", ["start_pump", "begin_maintenance", "power_off"]),
        ("water_pump", "running", ["stop_pump"]),
        ("grow_light", "idle", ["lights_on", "begin_maintenance", "power_off"]),
        ("grow_light", "running", ["lights_off"]),
        ("water_pump", "off", ["power_on"]),
        ("water_pump", "maintenance", ["end_maintenance"]),
        ("water_pump", "error", ["reset", "begin_maintenance"]),
    ],
)
def test_allowed_commands_depend_on_state_and_device_type(device_type, state, expected):
    assert ActuatorContext(device_type, state).allowed_commands() == expected


def test_unknown_device_type_gets_generic_start_and_stop():
    assert "start" in ActuatorContext("sprinkler", "idle").allowed_commands()


def test_error_is_a_system_event_never_a_user_command():
    for name in state_names():
        for device_type in ("water_pump", "grow_light"):
            assert "error" not in ActuatorContext(device_type, name).allowed_commands()


# --- Structure ---

def test_every_target_in_the_table_is_a_real_state():
    for name in state_names():
        for target in get_state(name).legal_targets():
            get_state(target)   # raises UnknownStateError if the table points nowhere


def test_state_interface_cannot_be_instantiated_without_transitions():
    class Broken(ActuatorState):
        name = "broken"

    with pytest.raises(TypeError):
        Broken()