import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="Integration tests need TEST_DATABASE_URL pointing at a *_test database",
)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from src.infrastructure.db import engine  # noqa: E402
from src.main import app  # noqa: E402

MISSING_ID = "00000000-0000-0000-0000-000000000000"


@pytest.fixture
def client():
    assert engine.url.database.endswith("_test"), "Refusing to wipe a non-test database"
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE actuator_states, automation_rules, sensor_readings, "
                "devices, zones, locations CASCADE"
            )
        )
    with TestClient(app) as c:
        yield c


# --- helpers ---

def kit(client, family="simulation"):
    res = client.post("/api/devices/provision", params={"family": family})
    assert res.status_code == 201, res.text
    return res.json()


def pump_and_light(client):
    devices = kit(client)
    pump = next(d for d in devices if d["device_type"] == "water_pump")
    light = next(d for d in devices if d["device_type"] == "grow_light")
    return pump, light, devices


def stored_state(device_id):
    """The state row in the database, or None when the device has no row yet."""
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT state FROM actuator_states WHERE device_id = :id"), {"id": device_id}
        ).scalar_one_or_none()


def row_count(device_id) -> int:
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT count(*) FROM actuator_states WHERE device_id = :id"), {"id": device_id}
        ).scalar_one()


def transition(client, device_id, target):
    return client.post(f"/api/devices/{device_id}/transition", json={"target": target})


# --- Device read models ---

def test_actuators_expose_state_and_commands_and_sensors_do_not(client):
    pump, light, devices = pump_and_light(client)
    listed = {d["id"]: d for d in client.get("/api/devices").json()}

    assert listed[pump["id"]]["state"] == "idle"
    assert listed[pump["id"]]["allowed_commands"] == ["start_pump", "begin_maintenance", "power_off"]
    assert listed[light["id"]]["allowed_commands"][0] == "lights_on"

    sensor = next(d for d in devices if d["role"] == "sensor")
    assert listed[sensor["id"]]["state"] is None
    assert listed[sensor["id"]]["allowed_commands"] == []


# --- Persistence: updated on a legal move only ---

def test_legal_transition_updates_the_row(client):
    pump, _, _ = pump_and_light(client)
    assert row_count(pump["id"]) == 0          # provisioned after the migration: no row yet

    res = transition(client, pump["id"], "running")

    assert res.status_code == 200, res.text
    assert res.json() == {
        "device_id": pump["id"],
        "state": "running",
        "allowed_commands": ["stop_pump"],
    }
    assert stored_state(pump["id"]) == "running"     # the first legal move created the row

    transition(client, pump["id"], "idle")
    assert stored_state(pump["id"]) == "idle"        # and later moves update it


def test_illegal_transition_does_not_update_row(client):
    pump, _, _ = pump_and_light(client)
    assert transition(client, pump["id"], "running").status_code == 200

    res = transition(client, pump["id"], "off")      # running → off is not allowed

    assert res.status_code == 409
    assert "Legal targets: idle, error" in res.json()["detail"]
    assert stored_state(pump["id"]) == "running"     # unchanged


def test_illegal_first_move_does_not_create_a_row(client):
    pump, _, _ = pump_and_light(client)

    assert transition(client, pump["id"], "idle").status_code == 409   # idle → idle
    assert row_count(pump["id"]) == 0

    after = next(d for d in client.get("/api/devices").json() if d["id"] == pump["id"])
    assert after["state"] == "idle"                  # still resolves to the initial state


# --- Error mapping ---

def test_unknown_target_state_is_400_and_saves_nothing(client):
    pump, _, _ = pump_and_light(client)
    res = transition(client, pump["id"], "nope")
    assert res.status_code == 400
    assert row_count(pump["id"]) == 0


def test_sensor_cannot_transition(client):
    sensor = next(d for d in kit(client) if d["role"] == "sensor")
    assert transition(client, sensor["id"], "running").status_code == 400


def test_missing_device_is_404(client):
    assert transition(client, MISSING_ID, "running").status_code == 404


# --- The zone device list (where the user opens controls) carries state too ---

def test_zone_device_list_includes_state(client):
    res = client.post(
        "/api/locations/config",
        json={
            "location_name": "State Bay",
            "zones": [
                {"name": "North", "moisture_threshold_low": 0.2, "moisture_threshold_high": 0.4},
            ],
        },
    )
    assert res.status_code in (200, 201), res.text
    body = res.json()
    location_id, zone_id = body["location"]["id"], body["zones"][0]["id"]

    pump, _, _ = pump_and_light(client)
    assigned = client.patch(f"/api/devices/{pump['id']}/zone", json={"zone_id": zone_id})
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["state"] == "idle"        # the assignment response carries it too

    assert transition(client, pump["id"], "running").status_code == 200
    zone_devices = client.get(f"/api/locations/{location_id}/zones/{zone_id}/devices").json()

    [listed] = zone_devices
    assert listed["id"] == pump["id"]
    assert listed["state"] == "running"
    assert listed["allowed_commands"] == ["stop_pump"]