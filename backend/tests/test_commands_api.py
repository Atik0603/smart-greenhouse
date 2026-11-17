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
                "TRUNCATE command_log, actuator_execution_log, actuator_states, automation_rules, "
                "sensor_readings, devices, zones, locations CASCADE"
            )
        )
    with TestClient(app) as c:
        yield c


# --- helpers ---

def kit(client):
    res = client.post("/api/devices/provision", params={"family": "simulation"})
    assert res.status_code == 201, res.text
    return res.json()


def of_type(devices, device_type):
    return next(d for d in devices if d["device_type"] == device_type)


def send(client, command_type, device_id, payload=None):
    body = {"command_type": command_type, "device_id": device_id}
    if payload is not None:
        body["payload"] = payload
    return client.post("/api/commands", json=body)


def state_of(client, device_id):
    return next(d for d in client.get("/api/devices").json() if d["id"] == device_id)["state"]


def scalar(sql, **params):
    with engine.connect() as conn:
        return conn.execute(text(sql), params).scalar_one()


def command_rows(device_id):
    return scalar("SELECT count(*) FROM command_log WHERE device_id = :id", id=device_id)


def execution_rows(device_id):
    return scalar("SELECT count(*) FROM actuator_execution_log WHERE device_id = :id", id=device_id)


def age_running(device_id):
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE actuator_states SET updated_at = now() - interval '31 minutes' WHERE device_id = :id"),
            {"id": device_id},
        )


# --- The two named acceptance tests ---

def test_start_pump_transitions_to_running(client):
    pump = of_type(kit(client), "water_pump")

    res = send(client, "start_pump", pump["id"])

    assert res.status_code == 200, res.text
    body = res.json()
    assert set(body) == {"id", "command_type", "device_id", "payload", "status", "error_message", "created_at"}
    assert body["status"] == "success"
    assert body["error_message"] is None
    assert state_of(client, pump["id"]) == "running"
    assert scalar("SELECT state FROM actuator_states WHERE device_id = :id", id=pump["id"]) == "running"
    assert command_rows(pump["id"]) == 1
    assert execution_rows(pump["id"]) == 1                    # went through the decorated port


def test_illegal_command_rejected_logged(client):
    pump = of_type(kit(client), "water_pump")                 # idle: stop is not allowed

    res = send(client, "stop_pump", pump["id"])

    assert res.status_code == 409
    body = res.json()
    assert body["status"] == "rejected"                       # same row shape as 200
    assert "while the actuator is idle" in body["error_message"]
    assert state_of(client, pump["id"]) == "idle"
    assert scalar("SELECT count(*) FROM actuator_states WHERE device_id = :id", id=pump["id"]) == 0
    assert execution_rows(pump["id"]) == 0                    # never reached the port
    history = client.get("/api/commands").json()
    assert history[0]["id"] == body["id"]                     # still in the history


# --- failed: policy after acceptance ---

def test_max_run_time_failure_is_logged_in_both_logs_and_state_kept(client):
    pump = of_type(kit(client), "water_pump")
    assert send(client, "start_pump", pump["id"]).json()["status"] == "success"
    age_running(pump["id"])

    res = send(client, "stop_pump", pump["id"])

    assert res.status_code == 200
    assert res.json()["status"] == "failed"
    assert res.json()["error_message"] == "Max run time exceeded"
    assert state_of(client, pump["id"]) == "running"
    blocked = client.get("/api/actuators/executions", params={"limit": 1}).json()[0]
    assert blocked["success"] is False
    assert blocked["policy_applied"] == ["maxRunTime", "logging"]


# --- set_light_level ---

def test_set_light_level_defaults_and_only_transitions_once(client):
    light = of_type(kit(client), "grow_light")

    first = send(client, "set_light_level", light["id"])
    assert first.status_code == 200
    assert first.json()["payload"] == {"level": 1}
    assert state_of(client, light["id"]) == "running"

    second = send(client, "set_light_level", light["id"], {"level": 60})
    assert second.json()["status"] == "success"
    assert state_of(client, light["id"]) == "running"


# --- 400 / 404: no row ---

@pytest.mark.parametrize(
    "command_type, payload",
    [("dance", None), ("set_light_level", {"level": 250})],
)
def test_bad_type_or_payload_is_400_and_writes_no_row(client, command_type, payload):
    light = of_type(kit(client), "grow_light")
    assert send(client, command_type, light["id"], payload).status_code == 400
    assert command_rows(light["id"]) == 0


def test_missing_device_or_sensor_is_404_and_writes_no_row(client):
    sensor = next(d for d in kit(client) if d["role"] == "sensor")
    assert send(client, "start_pump", sensor["id"]).status_code == 404
    assert send(client, "start_pump", MISSING_ID).status_code == 404
    assert scalar("SELECT count(*) FROM command_log") == 0


# --- history ---

def test_history_is_newest_first_and_limit_is_validated(client):
    pump = of_type(kit(client), "water_pump")
    send(client, "start_pump", pump["id"])
    send(client, "start_pump", pump["id"])                    # now rejected
    send(client, "stop_pump", pump["id"])

    rows = client.get("/api/commands", params={"limit": 10}).json()
    assert [(r["command_type"], r["status"]) for r in rows] == [
        ("stop_pump", "success"),
        ("start_pump", "rejected"),
        ("start_pump", "success"),
    ]
    assert len(client.get("/api/commands", params={"limit": 1}).json()) == 1
    assert client.get("/api/commands", params={"limit": 0}).status_code == 422
    assert client.get("/api/commands", params={"limit": 201}).status_code == 422