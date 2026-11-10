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
                "TRUNCATE actuator_execution_log, actuator_states, automation_rules, "
                "sensor_readings, devices, zones, locations CASCADE"
            )
        )
    with TestClient(app) as c:
        yield c


# --- helpers ---

def kit(client, family="simulation"):
    res = client.post("/api/devices/provision", params={"family": family})
    assert res.status_code == 201, res.text
    return res.json()


def a_pump(client):
    return next(d for d in kit(client) if d["device_type"] == "water_pump")


def apply(client, device_id, command="anything"):
    return client.post(f"/api/actuators/{device_id}/apply", json={"command": command})


def log_rows(device_id):
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT success, policy_applied, message FROM actuator_execution_log "
                "WHERE device_id = :id ORDER BY created_at"
            ),
            {"id": device_id},
        ).all()
    return [tuple(r) for r in rows]


def total_rows() -> int:
    with engine.connect() as conn:
        return conn.execute(text("SELECT count(*) FROM actuator_execution_log")).scalar_one()


def make_running_too_long(client, device_id):
    res = client.post(f"/api/devices/{device_id}/transition", json={"target": "running"})
    assert res.status_code == 200, res.text
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE actuator_states SET updated_at = now() - interval '31 minutes' "
                "WHERE device_id = :id"
            ),
            {"id": device_id},
        )


# --- Rows are inserted for every attempt ---

def test_successful_apply_inserts_a_success_row(client):
    pump = a_pump(client)

    res = apply(client, pump["id"], "anything")

    assert res.status_code == 200, res.text
    assert res.json()["command"] == "anything"
    assert log_rows(pump["id"]) == [(True, ["logging"], None)]


def test_failed_policy_writes_execution_row(client):
    pump = a_pump(client)
    make_running_too_long(client, pump["id"])

    res = apply(client, pump["id"], "stop_pump")

    assert res.status_code == 409
    assert res.json()["detail"] == "Max run time exceeded"
    assert log_rows(pump["id"]) == [(False, ["maxRunTime", "logging"], "Max run time exceeded")]


def test_running_for_less_than_the_limit_still_succeeds(client):
    pump = a_pump(client)
    assert client.post(
        f"/api/devices/{pump['id']}/transition", json={"target": "running"}
    ).status_code == 200

    assert apply(client, pump["id"], "stop_pump").status_code == 200
    assert log_rows(pump["id"]) == [(True, ["logging"], None)]


# --- The executions endpoint ---

def test_executions_endpoint_lists_newest_first(client):
    pump = a_pump(client)
    assert apply(client, pump["id"]).status_code == 200
    make_running_too_long(client, pump["id"])
    assert apply(client, pump["id"]).status_code == 409

    rows = client.get("/api/actuators/executions", params={"limit": 10}).json()

    assert [r["success"] for r in rows] == [False, True]          # newest first
    assert set(rows[0]) == {"id", "device_id", "success", "policy_applied", "message", "created_at"}
    assert rows[0]["policy_applied"] == ["maxRunTime", "logging"]
    assert rows[0]["message"] == "Max run time exceeded"
    assert rows[1]["message"] is None

    assert len(client.get("/api/actuators/executions", params={"limit": 1}).json()) == 1


# --- Not an execution attempt: no row ---

def test_missing_device_or_sensor_writes_no_row(client):
    sensor = next(d for d in kit(client) if d["role"] == "sensor")

    assert apply(client, sensor["id"]).status_code == 400
    assert apply(client, MISSING_ID).status_code == 404
    assert total_rows() == 0