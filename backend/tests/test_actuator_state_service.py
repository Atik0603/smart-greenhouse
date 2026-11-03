import uuid
from types import SimpleNamespace

import pytest

from src.application.devices.actuator_state_service import ActuatorStateService
from src.domain.actuators.errors import IllegalTransitionError, NotAnActuatorError
from src.domain.devices.errors import DeviceNotFoundError


def device(role="actuator", device_type="water_pump"):
    # The service only reads id, role and device_type.
    return SimpleNamespace(id=uuid.uuid4(), role=role, device_type=device_type)


class FakeDevices:
    def __init__(self, *devices):
        self.by_id = {d.id: d for d in devices}

    def get_device(self, device_id):
        return self.by_id.get(device_id)


class FakeStates:
    def __init__(self, stored=None):
        self.stored = dict(stored or {})
        self.saves = []
        self.get_states_calls = 0

    def get_states(self, device_ids):
        self.get_states_calls += 1
        return {i: self.stored[i] for i in device_ids if i in self.stored}

    def get_state(self, device_id):
        return self.stored.get(device_id, "idle")

    def save_state(self, device_id, state):
        self.saves.append((device_id, state))
        self.stored[device_id] = state


def service(*devices, stored=None):
    states = FakeStates(stored)
    return ActuatorStateService(FakeDevices(*devices), states), states


# --- The safety rule: transition first, save only afterwards ---

def test_legal_transition_is_saved():
    pump = device()
    svc, states = service(pump)

    view = svc.transition(pump.id, "running")

    assert view.state == "running"
    assert view.allowed_commands == ["stop_pump"]
    assert states.saves == [(pump.id, "running")]


def test_illegal_transition_saves_nothing():
    pump = device()
    svc, states = service(pump, stored={pump.id: "running"})

    with pytest.raises(IllegalTransitionError):
        svc.transition(pump.id, "off")

    assert states.saves == []
    assert states.stored[pump.id] == "running"


def test_actuator_without_a_stored_row_starts_idle():
    pump = device()
    svc, _ = service(pump)
    assert svc.get(pump.id).state == "idle"


# --- Errors ---

def test_unknown_device_is_not_found():
    svc, _ = service()
    with pytest.raises(DeviceNotFoundError):
        svc.transition(uuid.uuid4(), "running")


def test_sensor_has_no_lifecycle():
    sensor = device(role="sensor", device_type="moisture_sensor")
    svc, states = service(sensor)

    with pytest.raises(NotAnActuatorError):
        svc.transition(sensor.id, "running")
    assert states.saves == []


# --- List view ---

def test_views_cover_only_actuators_and_use_one_state_query():
    pump, light = device(), device(device_type="grow_light")
    sensor = device(role="sensor", device_type="moisture_sensor")
    svc, states = service(pump, light, sensor, stored={pump.id: "running"})

    views = svc.views_for([pump, light, sensor])

    assert set(views) == {pump.id, light.id}                 # no sensor entry
    assert views[pump.id].state == "running"
    assert views[light.id].allowed_commands[0] == "lights_on"
    assert states.get_states_calls == 1                      # not one query per device